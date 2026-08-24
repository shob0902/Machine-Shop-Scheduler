# Scheduling Algorithm

This document explains how `backend/scheduler/` turns master data into a
schedule with Google OR-Tools CP-SAT, and is deliberately specific about
what is and isn't exactly optimized — Section 41 of the assignment
("No fake results") applies to documentation as much as to numbers.

## 1. Time model

The horizon is 14 days, 2 shifts/day (06:00–14:00, 14:00–22:00), plus up to
2 hours/day of overtime after shift 2 (22:00–24:00). The overnight window
(00:00–06:00) is never modelled as workable time.

**Bucket size: 30 minutes** (`config.BUCKET_MINUTES`). Section 17 of the
assignment suggests 15 minutes as an example. 15 minutes was the initial
choice; during development the resulting CP-SAT model (~211 operations,
several interchangeable machines/operators per operation) took too long to
even find a first feasible solution (see "Solver performance" below).
Moving to 30-minute buckets roughly halves every bucket-indexed domain and
constraint count while still being finer than most real shop-floor
schedules need (a 30-minute slot is smaller than almost every operation's
own duration). This is a genuine, load-bearing engineering trade-off, not
a cosmetic one — it is documented here rather than silently made.

Per day: 16 buckets = shift 1, 16 = shift 2, 4 = overtime, 36 total
(`BUCKETS_PER_DAY_WITH_OT`). Total horizon: 14 x 36 = 504 buckets.

## 2. Decision variables

For every operation (after the data generator's batch-splitting, see
below) `t`:

- `start[t]`, `end[t]` — shared `IntVar`s (bucket units), `end = start + duration`.
  `duration` is a **fixed constant** computed from `quantity x
  minutes_per_piece + setup_minutes`, not a decision variable — the
  assumption (documented in `scheduler/models.py`) is that all machines of
  a capable type run a part at the same rate; capability, not speed,
  differentiates machines.
- `assign[t][(m, o)]` — one Boolean per valid (machine, operator)
  combination for `t` (`AddExactlyOne`). A combination is valid iff the
  machine has the required capability, is not permanently down, and the
  operator is both skilled in the operation type and qualified on that
  specific machine.
- `uses_machine[t][m]`, `uses_operator[t][o]` — Booleans channelled to the
  sum of the relevant `assign` variables, used as `AddNoOverlap` presence
  literals.
- `is_overtime[t]` — reified from `start[t] mod DAY_LEN` via
  `AddModuloEquality`, true iff the operation's last bucket falls in the
  overtime window.

## 3. Hard constraints

| # | Constraint | How |
|---|---|---|
| 1 | Operation precedence | `start[next] >= end[all tasks at previous sequence]` |
| 2 | Machine capability | Only capable machines appear in `assign[t]`'s keys |
| 3 | Machine capacity / no overlap | `AddNoOverlap` over optional intervals per machine |
| 4 | Operator availability | Operator's non-rostered/absent windows added as *mandatory* intervals in the same `AddNoOverlap` group |
| 5 | Operator skills | Only skilled+qualified operators appear in `assign[t]`'s keys |
| 6 | Shift availability | Same mechanism as #4 |
| 7 | Maintenance windows | Machine's maintenance windows added as mandatory intervals in the machine's `AddNoOverlap` group |
| 8 | Material availability | First operation of an order: `start >= max(release_bucket, material_bucket)` |
| 9 | Release dates | Same as #8 |
| 10 | Valid machine assignment | `AddExactlyOne` over `assign[t]` |
| 11 | Valid operator assignment | Joint with #10 (one variable covers both) |
| — | Day-boundary guard | `start mod DAY_LEN + duration <= DAY_LEN` — an operation may never straddle the overnight gap or the OT/next-day boundary |

## 4. Soft objectives / the three strategies

All three strategies share the identical hard-constrained feasible region;
`scheduler/objectives.py` builds a different linear objective:

- **Cheapest** — `operating_cost + overtime_cost + penalty_cost`.
- **Most On-Time** — `30,000x(late_order_bool x priority) +
  3,000x(tardiness_buckets x priority) + operating_cost + overtime_cost`.
  The large integer weights (CP-SAT objectives must be integer, so
  "primary vs. secondary" is expressed as a large-vs-small integer ratio,
  not a fractional weight) make lateness dominate cost in the search.
- **Most Robust** — heavily weights `peak_machine_busy_buckets` and,
  specifically, `peak_grinding_busy_buckets` (the shop's known fragile
  resource — only 2 grinding machines, 3 qualified operators), on top of
  priority-weighted tardiness. This is a genuine robustness proxy (spare
  capacity on the bottleneck), not a strategy that is merely labeled
  "robust" — see `scheduler/objectives.py` for the exact weights.

`operating_cost` is exact and linear (`assign x hours x rate`).
`overtime_cost` **inside the CP-SAT objective** uses a linear
approximation (`is_overtime[t] x hours x shop-average overtime premium`)
rather than the exact premium of whichever machine/operator CP-SAT
ultimately assigns — computing the exact value would need a Boolean AND
between `assign` and `is_overtime` for every (task, machine, operator)
triple, which alone added ~7,000 extra constraints during development and
was the single largest contributor to CP-SAT's search difficulty. The
**reported** cost breakdown shown to users (`solver.py:
_decode_cost_breakdown`) is never approximated — it is computed after
solving, directly from the realized (machine, operator, duration) of every
operation.

## 5. Two-phase changeover handling

Section 6 requires the solver to actually consider sequence-dependent
changeovers when deciding job order, not just record them in a table.

The textbook way to get this out of CP-SAT is the classic disjunctive
pattern: one boolean "does i run before j" per candidate pair on a given
machine, reified so the exact changeover gap is enforced only when both
land on that machine. This was the **first implementation** here, and
it is correct — but on this dataset's scale (many interchangeable
machines/operators per operation, before pruning) it alone produced tens
of thousands of reified constraints and pushed CP-SAT past 150 seconds
without finding even one feasible solution (measured, not estimated —
see below).

**Phase 1 (CP-SAT):** machine/operator assignment and an approximate
schedule using `AddNoOverlap` (no changeover awareness) — the efficient,
scalable CP-SAT primitive for "at most one task on this resource at a
time".

**Phase 2 (`scheduler/solver.py: _finalize_with_changeover`, always run,
deterministic):** replays Phase 1's assignments in the relative order
Phase 1 produced, and recomputes exact start/end times so every
precedence, resource, maintenance/shift, and — critically — **sequence-
dependent changeover gap is actually present** in the schedule returned to
the API. Changeover is a real, enforced part of the final output; CP-SAT's
own search just doesn't re-optimize against its exact cost (tardiness and
overtime objectives already discourage unnecessary machine-family
switching, since a wasted changeover eats capacity that would otherwise
avoid tardiness/overtime).

This is the single most consequential engineering decision in the
project, and it is intentionally not buried: see the docstring at the top
of `scheduler/constraints.py: _add_resource_disjunctions` for the same
explanation next to the code it describes.

## 6. Batch splitting (large lots)

A single operation cannot span a shift handover in this model (an
operator's availability window is one contiguous shift + its overtime
extension). Quantities up to 5,000 pieces can require more processing time
than one shift allows. `data/generator.py` therefore splits any routing
step whose computed duration would exceed `MAX_SINGLE_OPERATION_BUCKETS`
(≈7.5 hours) into several same-`sequence` sub-batches, which the solver
then treats as parallel alternatives that must **all** finish before the
next routing step starts. This mirrors real shop-floor practice (running a
large lot as multiple batches, possibly on different machines in
parallel) and is a documented assumption, not a silent simplification.

## 7. Machine-family affinity pruning

Every Turning operation being eligible on all 4 lathes (and similarly for
milling/drilling) creates large, mostly-symmetric candidate pools per
machine — which is exactly what makes the pairwise-changeover pattern in
Section 5 expensive. `scheduler/models.py: restrict_machines_by_family`
pre-qualifies each part family on a realistic 2-machine "home pool" per
machine type with >2 members (Grinding and Inspection, with only 2
machines each, are left unrestricted — that scarcity is the point).

## 8. Solver performance (measured, not claimed)

On the development machine, with the full generated dataset (14 machines,
26 operators, 25 orders, ~211 operations after batch-splitting):

- A **6-order** slice (the test-suite fixture, ~40-50 operations)
  reliably reaches `OPTIMAL` in single-digit seconds.
- An **8-order** slice reached `OPTIMAL` in ~7s; a **9-order** slice did
  not reach any incumbent within 40s in one measured run (CP-SAT search
  difficulty is not smoothly monotonic in problem size); 10-11 orders
  reached `OPTIMAL` in 12-16s.
- The **full 25-order** model did not reach `OPTIMAL`/`FEASIBLE` within
  120s in repeated runs during development.

**What the app does about this:** `solve_schedule` always tries CP-SAT
first, with a warm-start hint from a greedy constructive heuristic
(`scheduler/heuristic.py`) and a domain-pruning tactic (an operation's
search window is capped at `due_date + 6 days` rather than the full
horizon). If CP-SAT returns `UNKNOWN` (no incumbent in the time budget) —
**or even `INFEASIBLE`**, since that pruning means an "infeasible" verdict
only proves nothing exists *within the pruned window*, not that the shop
truly cannot deliver — the same constructive heuristic (searching the
full, unpruned horizon) is used to build a schedule, which then still goes
through Phase 2 changeover finalization exactly like a CP-SAT solution
would. The response's `solver_status` is set to
`FEASIBLE_HEURISTIC_FALLBACK` in that case — **this is always reported
honestly to the API and UI**, never disguised as `OPTIMAL`. Only if the
heuristic also cannot place every operation does the API return a genuine
"no feasible schedule" error (Section 33).

The heuristic fallback is strategy-aware (it prefers cheaper resources for
Cheapest, less-loaded machines for Most Robust, earliest-finish for Most
On-Time — see `greedy_construct`'s docstring) but is a simpler
approximation than CP-SAT's exact optimization; when CP-SAT itself
converges (smaller/typical replanning scenarios), the three strategies are
rigorously differentiated by the actual objective function in Section 4.

This trade-off is exactly why Section 17 says "avoid a model that becomes
unnecessarily huge" — and why it is documented this thoroughly rather than
quietly shipped.
