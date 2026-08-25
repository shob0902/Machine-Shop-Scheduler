# Disruption Replanning

This is the heart of the system - reacting to disruption in minutes, not
hours. This document explains the algorithm in
`backend/scheduler/replanner.py` and `backend/services/disruption_service.py`.

## Flow

```
Current schedule (from the database - the last generate/replan result)
    |
Disruption arrives (machine_breakdown | operator_absence |
                     material_delay | rework | power_cut)
    |
Freeze completed work        (operation.end_bucket <= now_bucket)
Freeze in-progress work       (start_bucket <= now_bucket < end_bucket),
                               UNLESS the disruption itself interrupts it
                               (its machine just went down / its operator
                               just became absent / its order's material
                               just got delayed) - this "preserve
                               already-started work where possible" is
                               honored precisely: only work the disruption
                               actually hits gets un-frozen.
    |
Apply the disruption as a constraint Overlay:
    machine_breakdown  -> extra blocked bucket range on that machine
    operator_absence   -> that operator unavailable for that (day, shift)
    material_delay     -> a later material-available bucket for the order
    rework             -> inject a new task into the routing
    power_cut          -> block every machine for that (day, shift)
                           UNLESS use_generator=true, in which case no
                           scheduling constraint changes - it is priced
                           as a cost line item instead
    |
Re-solve with scheduler.solve_schedule(..., overlay=...) - frozen
operations are passed back in as HARD-FIXED (machine, operator, start,
end); CP-SAT (or its heuristic fallback) can only move what has not
actually happened yet. This is why the result is not "a completely new
schedule" - it is the same schedule
with only the future re-optimized.
    |
Diff old vs. new schedule, operation-by-operation and order-by-order
    |
Price the difference (cost_delta = new_cost_breakdown - old_cost_breakdown)
    |
Generate the data-driven "owner action" recommendation
```

## Why not just regenerate from scratch?

Because this says not to, and because it would be operationally
useless: a shop floor supervisor cannot tell 8 operators mid-shift "your
job just changed" for work that was never actually affected. Freezing
completed/in-progress work and only re-optimizing the future is both the
assignment's explicit requirement and the only version of this feature a
real shop could use.

## What the comparison shows

`ReplanComparison` (returned as `data.comparison` from
`POST /api/schedule/replan` and every `/api/disruptions/*` endpoint):

- `moved_operations` — every operation whose machine, operator, or start
  time changed (or that is brand new, e.g. an injected rework batch).
- `order_changes` — per order: old vs. new promised completion, old vs.
  new status (🟢 ON_TRACK / 🟡 AT_RISK / 🔴 LATE), whether it moved, whether
  it became newly late.
- `newly_late_orders`, `new_overtime_operations` — the headline numbers a
  supervisor actually needs.
- `cost_delta` — every cost component's before/after difference.
- `disruption_cost` — `cost_delta.total_cost`, i.e. exactly what this
  disruption cost the shop, in the same currency units as everything
  else.
- `wasted_changeover_minutes_delta`.

## Demo scenario walkthrough

```
POST /api/disruptions/breakdown
{
  "machine_id": "GRIND-01",
  "start_time": "2026-08-25T11:00:00",   <- "Tuesday 11 AM"
  "duration_minutes": 480,                <- "8+ hours"
  "reason": "Bearing failure"
}
```

`now_bucket` defaults to the breakdown's own start time when not supplied
(the natural reading of "now" for this scenario) — everything already
running or finished by 11:00 stays frozen; everything not yet started, and
anything running on GRIND-01 at that exact moment, is re-optimized. A
second call to `/api/disruptions/operator-absence` for one of the three
grinding-qualified operators layers on top the same way. Because only 2
grinding machines and 3 grinding operators exist in the generated data
, this scenario is
genuinely tight and the solver's response (which orders slip, how much
overtime gets added, whether the Tier-1 customer's Thursday delivery
survives) is not scripted — it is whatever CP-SAT (or its documented
fallback) actually produces for that day's real state. See
`docs/screenshots/disruptions_after_replan.png` for the actual captured
output of running this exact scenario against a live instance of the app.

## The owner action recommendation

`services/disruption_service.py: generate_owner_action` is **not** a
template string. It reads `comparison.order_changes`, picks the order that
moved worst-weighted by customer tier and how late it slipped, and reads
the actual `cost_delta.penalty_cost` / `cost_delta.overtime_cost` to write
the reason:

- If the penalty cost went up, it says how much the penalty is if nothing
  changes with the customer.
- If overtime went up, it says how much holding the original date is
  currently costing.
- If the disruption was fully absorbed with no order impact, it says so
  explicitly (`has_action: false`) instead of manufacturing a call to
  make.

## Quality / rework

A rework event (`POST /api/disruptions/rework`) injects a new task into
the affected order's routing, at `~60%` of the referenced operation's
per-piece rate (an approximation of "redo, not re-fixture from scratch" —
documented in `scheduler/models.py`), sequenced immediately after the
operation it reworks. It re-enters the normal CP-SAT/heuristic scheduling
path exactly like any other operation — no special-cased logic.

## Power cut / generator

`POST /api/disruptions/power-cut` with `use_generator: false` blocks the
named shift shop-wide, forcing every affected operation to be replanned to
another shift/machine. With `use_generator: true`, no scheduling
constraint is added — the shift proceeds as planned, and
`services/cost_service.py: price_power_cut` prices the affected
operations at `GENERATOR_COST_MULTIPLIER` (3x, this) instead of the
normal machine rate, surfaced as a note on the replan result.
