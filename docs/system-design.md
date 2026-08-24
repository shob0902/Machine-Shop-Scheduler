# System Design

See [architecture.md](architecture.md) for diagrams; this document is the
component-by-component narrative.

## Frontend (`frontend/src/`)

React + TypeScript, built with Vite, styled with Tailwind CSS v4. State is
kept deliberately simple: a `StrategyProvider` React Context
(`hooks/useStrategy.tsx`) holds the currently-selected strategy (persisted
to `localStorage`) and a `refreshKey` counter pages watch to know when to
refetch after a generate/replan action, plus per-page `useState`/`useEffect`
data fetching through a typed Axios client (`services/api.ts`). No global
state library was needed at this scope.

Pages (`pages/`): Dashboard, Schedule (Gantt), Orders, Machines,
Disruptions, StrategyComparison, CostAnalysis — one per Section 29
requirement. `components/Gantt.tsx` is a hand-built CSS-positioned Gantt
(machine rows x day/hour columns, colored by part family, click for
detail) rather than a chart-library Gantt, since none of Recharts'
built-in chart types fit a resource-timeline view well; Recharts is used
for the bar/pie charts on the Strategy Comparison and Cost Analysis pages,
where it is a good fit.

## Backend (`backend/`)

Flask app factory (`app.py: create_app`) registering one blueprint per
resource area (`routes/`). Every route delegates to a `services/` module —
routes never talk to the scheduler or the database directly, which keeps
the HTTP layer thin and testable independent of Flask
(`tests/test_scheduling.py`, `test_replanning.py`, `test_costs.py`,
`test_strategies.py` all call `scheduler.solve_schedule`/`replan` directly,
with no Flask test client involved).

## Data layer

Master data (machines/operators/orders/changeovers/breakdowns) is
generated once as JSON (`data/generator.py` -> `data/*.json`) — it is
reference data, regenerated deliberately (`POST /api/schedule/generate`
with `regenerate_data: true`), not something that needs relational
querying. Mutable application state — the active schedule per strategy,
the disruption log — lives in SQLite (`db.py`), so the API survives a
restart with its last-known state intact and `/api/disruptions` has real
history.

## Scheduling engine

See [scheduling-algorithm.md](scheduling-algorithm.md) in full. In brief:
`scheduler/models.py` turns raw JSON + an optional `Overlay` into flat
`Task` objects; `constraints.py` builds the CP-SAT model's variables and
hard constraints; `objectives.py` builds one of three linear objectives;
`solver.py` orchestrates solve -> (Phase 2 changeover finalization) ->
decode; `heuristic.py` provides both the CP-SAT warm-start hint and the
honestly-labeled fallback when CP-SAT cannot converge in time;
`replanner.py` is the disruption/replan orchestration described in
[disruption-replanning.md](disruption-replanning.md).

## Disruption engine

`services/disruption_service.py` translates the five raw disruption
payload shapes (Section 24) into `scheduler.models.Overlay`, drives
`scheduler.replanner.replan`, and generates the owner-action
recommendation. It is a service, not scattered across routes, so the same
logic backs both the generic `/api/disruptions` endpoint and the five
typed convenience endpoints.

## Cost engine

Two halves, deliberately separate (see
[scheduling-algorithm.md](scheduling-algorithm.md) section 4 for why):
a **linear approximation** lives inside the CP-SAT objective (so the
solver stays a tractable integer program), and the **exact** breakdown
(`solver.py: _decode_cost_breakdown`) is always computed after solving,
directly from the realized schedule. `services/cost_service.py` adds
presentation concerns on top (percentages, the generator-vs-lose-shift
pricing for power cuts) — it never recomputes core costs differently from
the solver's own decode step, so the number on the Cost Analysis page and
the number used to price a disruption are always the same number.

## Strategy engine

`services/strategy_service.py: compare_strategies` runs `solve_schedule`
three times (once per strategy), builds one comparison row per strategy
from that solve's own `metrics`/`cost_breakdown` (never a second,
separately-computed set of numbers), and scores a recommendation from
those real rows (`build_recommendation`) — see
[trade-off-memo.md](trade-off-memo.md) for a worked example with real
numbers from a captured run.
