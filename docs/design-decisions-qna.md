# Design Decisions Q&A

## 20 likely questions and strong answers

**1. Why did you choose OR-Tools?**
It's Google's constraint-programming/optimization suite, open source,
actively maintained, with a Python API that maps cleanly onto scheduling
problems (intervals, no-overlap, precedence) without hand-rolling a
solver. CP-SAT specifically (not the MIP or routing solvers) is built for
exactly this class of problem: discrete scheduling with resource
constraints.

**2. Why CP-SAT specifically?**
CP-SAT is a lazy-clause-generation SAT solver under the hood, which
handles the kind of disjunctive ("this OR that machine, not both at the
same time") and reified ("this constraint only applies if X is chosen")
logic that machine scheduling is full of, far better than a pure LP/MIP
solver would - and it has first-class `IntervalVar`/`NoOverlap` primitives
built for exactly this.

**3. Why Flask?**
Small, unopinionated, and the whole team of "endpoints" needed here (a
few dozen REST routes around a Python-native optimization core) doesn't
need Django's ORM/admin/auth machinery. Flask-CORS and Pydantic cover
what's actually needed (cross-origin requests from the Netlify frontend,
request validation).

**4. Why React?**
Component reuse (the Gantt, StatCard, StatusBadge are used across every
page), a mature ecosystem (Recharts, React Router), and it's the
explicitly requested stack.

**5. Why SQLite?**
Prototype scale,
zero operational overhead (no separate DB server to deploy alongside
Render's free tier), and the only things that actually need to persist
across requests here (active schedule per strategy, disruption log) are
small and simple enough that SQLite's lack of concurrent-write
sophistication is a non-issue.

**6. How does your scheduler handle machine constraints?**
Each operation's `assign` variable only has entries for `(machine,
operator)` pairs where the machine's `capabilities` list includes that
operation's type, is not down, and passes the family-affinity pool filter
(see scheduling-algorithm.md section 7). Capacity is enforced by
`AddNoOverlap` over optional intervals per machine.

**7. How do you handle operation precedence?**
A direct linear constraint: the start of every operation at routing step
`k+1` must be >= the end of every operation at step `k` for the same
order (`scheduler/constraints.py: _add_precedence`). Batch-split
sub-operations at the same step are treated as parallel alternatives that
must *all* finish before the next step starts.

**8. How do you model changeovers?**
A generated 6x6 part-family matrix (~15-25 min same-family, 45-180 min
cross-family). It's enforced in a Phase-2 deterministic pass that replays
the CP-SAT-chosen assignment/order and inserts every required gap for
real - see scheduling-algorithm.md section 5 for exactly why it's Phase 2
and not baked directly into the CP-SAT objective (a real, measured
tractability trade-off, not laziness).

**9. How do you handle operator absence?**
An `Overlay.operator_extra_absences` entry removes that (day, shift) from
the operator's availability, which is enforced as a mandatory blocked
interval in their `AddNoOverlap` group - the solver simply cannot place
any operation on them during that window, and any operation already
assigned there and not yet started gets un-frozen and re-optimized by the
replanner.

**10. How does replanning work?**
See docs/disruption-replanning.md in full: freeze completed/in-progress
work (unless the disruption itself hits it), apply the disruption as a
constraint overlay, re-solve only the non-frozen future, diff old vs. new,
price the difference.

**11. Why don't you simply regenerate the whole schedule?**
Because a shop floor can't act on that - operators already mid-job can't
be told their assignment changed, and a from-scratch replan would move
completed work's records for no reason. Freezing what already happened
and re-optimizing only the future is both the project's explicit
requirement and the only operationally sane behavior.

**12. How do you calculate late penalties?**
`tardiness_hours / 24 x order.late_penalty_per_day`, computed from the
solved order's actual completion vs. its due date - `solver.py:
_decode_cost_breakdown`.

**13. How do you decide whether overtime is cheaper than a penalty?**
We don't decide it with a rule - CP-SAT's objective (Cheapest strategy)
literally sums `overtime_cost + penalty_cost` alongside operating cost and
minimizes the total, so the solver itself trades them off per-operation
based on the real weighted cost of each option in the search. There's no
hardcoded "always prefer overtime" logic anywhere.

**14. What makes your third schedule "robust"?**
It explicitly minimizes peak machine utilization and, with extra weight,
peak utilization specifically on the 2 grinding machines - the shop's
named fragile bottleneck (only 3 qualified operators). A schedule that
keeps spare capacity on the busiest resource can absorb a breakdown
without the whole plan collapsing, which is what "robust" should mean
operationally, not just as a label - see scheduler/objectives.py.

**15. What happens if no feasible schedule exists?**
`SchedulingError` is raised with a specific message and a suggestion
, returned as HTTP 422 by every
route. The system tries hard not to say this falsely - see question 17.

**16. How would this scale to 1,000 orders?**
The current CP-SAT encoding already shows super-linear difficulty growth
well before 1,000 orders (see scheduling-algorithm.md's measured numbers
at 25 orders / ~211 operations). Getting there for real would need: (a)
a proper circuit-constraint changeover encoding instead of the current
Phase-2 split, (b) decomposition - solving per-machine-group or per-week
sub-problems and stitching, (c) tighter, demand-driven pruning of
candidate machine/operator pools, and (d) moving schedule generation to a
background job with progress streaming instead of a blocking HTTP call.

**17. What would you change for production?**
PostgreSQL over SQLite, real authentication, an async job queue for
schedule generation (with a job-status endpoint instead of a blocking
POST), real ERP/MES integration for orders and machine status, and the
circuit-constraint changeover model from Q16 once there's time budget to
build and validate it properly.

**18. Why didn't you use an LLM?**
Deliberately avoided for scheduling decisions - an LLM cannot guarantee hard-constraint satisfaction
(no double-booking a machine, no violating precedence) the way a
constraint solver can prove it. Every schedule this system returns is
either CP-SAT-proven feasible or built by a deterministic constructive
algorithm that is checked against the same hard constraints - never a
plausible-sounding guess.

**19. How would you integrate real machine data?**
Replace `services/data_service.py`'s JSON file reads with calls to the
shop's MES/PLC layer for machine status and an ERP for orders, feeding
the same `Machine`/`Order`/`Operator` Pydantic shapes already defined in
`backend/models/` - the scheduler itself is already decoupled from where
the data comes from.

**20. What would you do if the grinding machine failed for an entire
day?**
Exactly what `POST /api/disruptions/breakdown` with
`duration_minutes: 960`+ does today: freeze in-flight work, block that
machine for the full window, and let the replanner move every grinding
operation either to the other grinding machine (if a qualified operator
is free) or later in the horizon. The `owner_action` recommendation would
surface whichever customer order is most affected (weighted by tier and
how late it slipped) and the real cost of holding vs. moving that date.

## Walkthrough: the grinding-machine breakdown scenario

```
Tuesday 11 AM: GRIND-01 down, 8+ hours
One of the three grinding operators: absent
Tier-1 delivery: Thursday 6 AM
```

Run live: `docs/screenshots/disruptions_after_replan.png` is the actual
captured output of this exact scenario (see
disruption-replanning.md "Demo scenario walkthrough" for the
request body).

- **What changed?** GRIND-01 became unavailable for the breakdown window;
  everything on it not yet started (or interrupted mid-run) had to move.
- **What did the system detect?** In the captured run, 24 operations were
  already far enough along to freeze; 187 were re-optimized.
- **What operations were affected?** Every operation whose machine was
  GRIND-01, plus anything downstream of it via precedence.
- **What moved?** 48 operations in the captured run - some to GRIND-02,
  some to a later shift on GRIND-01, some rescheduled around the still-
  frozen work of other orders.
- **What stayed frozen?** Anything already completed, and anything
  in-progress that wasn't itself on the broken machine.
- **Which orders slipped?** 1 order became newly late in the captured
  run (`comparison.newly_late_orders`); the rest of the previously-late
  orders stayed late but at a different time, and previously on-track
  orders mostly stayed on-track.
- **How much did it cost?** Rs.6,136.31 in the captured run
  (`comparison.disruption_cost`) - overtime and penalty deltas shown in
  the UI screenshot.
- **What action should the owner take?** The system's own
  `owner_action.headline` in the captured run: call the affected
  customer about their order's new promised date, with the exact
  overtime/penalty numbers driving that recommendation - not a hardcoded
  sentence, generated fresh from that run's comparison.
- **Why?** Because the alternative - silently absorbing the disruption
  with overtime - was shown (via `cost_delta.overtime_cost`) to already
  be costing real money, and the recommendation engine's whole point is
  to make that visible instead of buried in a schedule nobody reads.
