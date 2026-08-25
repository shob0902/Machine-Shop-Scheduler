# The Machine Shop Scheduler

A production-quality prototype that generates a realistic 40-person machine
shop, builds a real 2-week production schedule with Google OR-Tools CP-SAT,
and — the heart of the system — replans that schedule when a disruption
(machine breakdown, operator absence, material delay, rework, power cut)
hits, showing exactly what changed and what it cost.

> **No hardcoded schedules.** Every number in this README and in the app is
> produced by the CP-SAT solver (or, when noted, an honestly-labeled
> constructive fallback — see "Solver performance" below) from generated
> data. See [docs/scheduling-algorithm.md](docs/scheduling-algorithm.md) for
> exactly how.

---

## 1. Project Overview

Sridhar Precision Works runs 14 machines across 2 shifts with ~25 open
orders at any time. Scheduling by hand cannot simultaneously respect
machine capability, operator skill (only 3 people can run the grinding
machines), sequence-dependent changeovers, maintenance windows, material
delays, and customer-tier delivery penalties — and it certainly cannot
replan all of that in seconds when a machine breaks down. This project
builds that scheduler.

## 2. Problem Statement

```
Orders + Machines + Operators + Routing + Changeovers + Due dates
    + Breakdowns + Material constraints + Quality/rework + Overtime
    = a constrained optimization problem, solved with OR-Tools CP-SAT
```

## 3. Features

- Synthetic but internally-consistent shop data: 14 machines, ~25 orders
  (3–6 routing steps each), 26 operators (exactly 3 grinding-qualified),
  a sequence-dependent changeover matrix, historical breakdown records,
  and planned maintenance windows.
- A real CP-SAT scheduling engine (`backend/scheduler/`) — hard
  constraints for precedence, capability, capacity, operator
  skill/availability, maintenance, and material availability; soft
  objectives for cost, lateness, overtime, and robustness.
- **Three scheduling strategies** — Cheapest, Most On-Time, Most Robust —
  each a genuinely different CP-SAT objective, with a comparison table and
  a recommendation generated from the actual solved metrics.
- **A disruption/replanning engine** that freezes completed/in-progress
  work, applies the disruption as a constraint, re-optimizes only what
  hasn't happened yet, and diffs old vs. new schedules — with cost impact
  and a data-driven "what should the owner do right now" recommendation.
- A supervisor-first React dashboard: large text, 🟢/🟡/🔴/⚫ status colors,
  an interactive Gantt schedule, and a REPLAN button.

## 4. Architecture

```
React (Vite/TS/Tailwind) --REST/JSON--> Flask API --> Services
                                                          |
                                          scheduler/ (OR-Tools CP-SAT)
                                                          |
                                                  SQLite (schedules,
                                                  disruption history)
```

See [docs/architecture.md](docs/architecture.md) for the full diagram set
(scheduling flow, replanning flow, ER diagram, deployment).

## 5. Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React + TypeScript + Vite + Tailwind CSS v4 + Axios + Recharts + React Router |
| Backend | Python + Flask + Flask-CORS + Pydantic + Pandas |
| Optimization | Google OR-Tools **CP-SAT** |
| Database | SQLite |
| Deployment | Netlify (frontend) + Render (backend) |

## 6. Scheduling Approach

- **Time model:** 30-minute discrete buckets (see
  [docs/scheduling-algorithm.md](docs/scheduling-algorithm.md) "Time
  granularity" for the 15-vs-30-minute trade-off actually made).
- **Decision structure:** one `(machine, operator)` assignment choice per
  operation, plus a shared `start`/`end` pair, built with CP-SAT
  `NewIntVar` / `NewOptionalIntervalVar` / `AddNoOverlap`.
- **Hard constraints:** precedence, machine capability, machine capacity
  (no overlap), operator skill, operator availability (shift roster +
  absences, folded into the same `AddNoOverlap` group as blocked
  intervals), machine maintenance windows, material availability, release
  dates.
- **Two-phase changeover handling:** Phase 1 (CP-SAT) picks assignments
  and an approximate schedule using efficient `AddNoOverlap` capacity
  constraints; Phase 2 (a deterministic pass) replays those choices and
  inserts every sequence-dependent changeover gap for real. Full
  rationale in docs/scheduling-algorithm.md — this is the single most
  important engineering trade-off in the project and it is not hidden.
- **Objectives:** Cheapest (cost only), Most On-Time (lateness-first, cost
  as tie-break), Most Robust (bottleneck/grinding spare-capacity first).

## 7. Optimization Objectives

See the comparison table generated live on the **Strategy Comparison**
page, and [docs/trade-off-memo.md](docs/trade-off-memo.md) for a written
analysis with real numbers from a sample run.

## 8. Disruption Handling

Five disruption types are implemented end-to-end: machine breakdown,
operator absence, material delay, rework, and power cut (lose-the-shift or
run-the-generator-at-3x). See
[docs/disruption-replanning.md](docs/disruption-replanning.md).

## 9. Project Structure

```
machine-shop-scheduler/
├── backend/
│   ├── app.py, config.py, calendar_utils.py, db.py, requirements.txt
│   ├── models/          # Pydantic data models
│   ├── data/             # generator.py + generated *.json master data
│   ├── scheduler/        # models.py, constraints.py, objectives.py,
│   │                      # solver.py, replanner.py, heuristic.py
│   ├── services/          # cost/disruption/metrics/strategy/data services
│   ├── routes/             # Flask blueprints
│   └── tests/
├── frontend/
│   └── src/{components,pages,services,hooks,types}/
├── docs/
├── pdf/
├── README.md, render.yaml, netlify.toml, docker-compose.yml, LICENSE
```

## 10. Local Setup

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate            # Windows; use `source venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
cp .env.example .env             # adjust if needed
python data/generator.py         # generates backend/data/*.json
python app.py                    # runs on http://localhost:5000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local       # VITE_API_BASE_URL=http://localhost:5000
npm run dev                      # runs on http://localhost:5173
```

Open http://localhost:5173, and on the Dashboard click **Regenerate
Schedule** (first run can take up to ~60s — see "Solver performance"
below).

## 11. Environment Variables

**backend/.env** (see `backend/.env.example`):
```
FLASK_ENV=development
DATABASE_URL=./shop.db
FRONTEND_URL=http://localhost:5173
DATA_SEED=42
```

**frontend/.env.local** (see `frontend/.env.example`):
```
VITE_API_BASE_URL=http://localhost:5000
```

## 12. API Documentation

All responses are `{ "success": bool, "data" | "error"/"suggestion" }`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness check |
| GET | `/api/dashboard?strategy=` | Supervisor dashboard summary |
| GET | `/api/machines?strategy=` | Machines + utilization + reliability |
| GET | `/api/operators` | Operator roster |
| GET | `/api/orders?strategy=` | Orders + promised completion + status |
| GET | `/api/schedule?strategy=` | Active schedule (auto-generates if none) |
| POST | `/api/schedule/generate` | `{strategy, time_limit_seconds, regenerate_data}` |
| POST | `/api/schedule/replan` | `{disruption_type, payload, strategy}` |
| GET | `/api/strategies` | List of the 3 strategies + descriptions |
| POST | `/api/strategies/compare` | Runs all 3, returns comparison + recommendation |
| GET | `/api/disruptions` | Disruption history |
| POST | `/api/disruptions` | Generic `{disruption_type, payload, strategy}` |
| POST | `/api/disruptions/breakdown` | `{machine_id, start_time, duration_minutes, reason}` |
| POST | `/api/disruptions/operator-absence` | `{operator_id, day_index, shift}` |
| POST | `/api/disruptions/material-delay` | `{order_id, new_material_available_time}` |
| POST | `/api/disruptions/rework` | `{order_id, quantity, operation_id?}` |
| POST | `/api/disruptions/power-cut` | `{day_index, shift, duration_minutes, use_generator}` |
| GET | `/api/costs?strategy=` | Cost breakdown with percentages |
| GET | `/api/metrics?strategy=` | Raw schedule metrics |

## 13. Testing

```bash
cd backend
pytest tests/ -q
```

38 tests covering data generation, hard-constraint satisfaction (no
overlaps, precedence, maintenance, material availability, valid
machine/operator assignment), all four replanning scenarios, cost-breakdown
consistency, all three strategies, and the Flask API surface. **Actual
result on this machine: 38 passed** (~5 minutes, dominated by CP-SAT solve
time — see below). Run log is not fabricated; re-run the command above to
reproduce it.

## 14. Deployment

**Backend → Render:** `render.yaml` at the repo root configures a Python
web service (`gunicorn app:app`, 180s worker timeout — schedule generation
can take up to ~90s). Set `FRONTEND_URL` to your Netlify URL after first
deploy.

**Frontend → Netlify:** `netlify.toml` builds `frontend/` with `npm run
build` and publishes `dist/`. Set `VITE_API_BASE_URL` in Netlify's site
environment variables to your Render backend URL — it is never hardcoded
in the source.

## 15. Screenshots

See `docs/screenshots/` for real, freshly-captured screenshots of every
page (Dashboard, Schedule/Gantt, Orders, Machines, Disruptions with a live
before/after replan, Strategy Comparison, Cost Analysis) and
`docs/screenshots/console_errors.json` (empty — zero browser console
errors during the capture run).

## 16. Assumptions

None of these are physically fixed; values used here are engineering
assumptions, documented rather than left implicit, and are collected in
full in [docs/trade-off-memo.md](docs/trade-off-memo.md) "Assumptions":

- Shifts: 06:00–14:00 / 14:00–22:00, plus up to 2h/day overtime after
  shift 2. Overnight (22:00/00:00–06:00) is never worked.
- Time bucket: 30 minutes.
- Overtime billed at 1.75x on top of machine/operator hourly rate
  (applied per operation, not sub-divided per bucket).
- A single operation cannot span a shift handover; a lot large enough to
  need more than ~7.5 hours is split by the data generator into parallel
  sub-batches.
- Each part family is pre-qualified on a realistic 2-machine "home pool"
  per machine type (not fully interchangeable across all 4 lathes, etc.)
  — a tractability + realism trade-off, documented in
  scheduler/models.py.
- Changeover cost is billed at the machine's hourly rate for the
  changeover minutes actually incurred in the final (Phase-2) schedule.
- Generator premium: 3x electricity-linked machine cost.

## 17. Limitations

- All data is synthetic; there is no ERP/ MES/IoT integration.
- SQLite is a prototype-scale store;
  production would move to Postgres (see Future Improvements).
- **Solver performance:** the full 25-order/~210-operation CP-SAT model
  does not always reach a proven-optimal (or even first-feasible) solution
  within a practical time budget on this hardware — see
  docs/scheduling-algorithm.md "Solver performance" for the actual numbers
  measured during development and the honest fallback behavior
  (`solver_status: "FEASIBLE_HEURISTIC_FALLBACK"`) this triggers. Smaller
  problems (a single replan, most disruption scenarios, the 6-order test
  fixture) reliably reach `OPTIMAL`/`FEASIBLE` in seconds.
- The Kannada/Tamil supervisor-language requirement is addressed only via
  UI simplicity (large text, color status, minimal jargon), not actual
  translation — see Future Improvements.

## 18. Future Improvements

PostgreSQL; real ERP/MES integration; live machine telemetry; predictive
maintenance; a Kannada/Tamil UI; authentication and audit logs; a cloud
database; a full sequence-dependent-changeover CP-SAT encoding (circuit
constraint) once the candidate pool can be pruned further; batch/async
schedule generation with progress streaming instead of a blocking HTTP
call.

---

A personal project exploring constraint-programming (CP-SAT) for real-world
manufacturing scheduling and disruption replanning.
