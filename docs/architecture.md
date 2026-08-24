# Architecture Diagrams

## 1. Overall system architecture

```mermaid
flowchart TD
    U[Supervisor / User] --> FE[React Frontend<br/>Vite + TS + Tailwind]
    FE -->|REST/JSON, Axios| API[Flask REST API]
    API --> RT[routes/*.py blueprints]
    RT --> SV[services/*.py]
    SV --> SCH[scheduler/ - OR-Tools CP-SAT]
    SV --> DB[(SQLite<br/>schedules, disruptions)]
    SCH --> DATA[data/*.json<br/>machines, operators, orders, changeovers]
```

## 2. Scheduling flow

```mermaid
flowchart TD
    A[Master data: machines, operators, orders, changeovers] --> B[scheduler/models.py<br/>build_solver_input]
    B --> C[scheduler/constraints.py<br/>build_model - hard constraints]
    C --> D[scheduler/objectives.py<br/>build_objective - strategy-specific]
    D --> E[scheduler/heuristic.py<br/>greedy_construct - warm-start hint]
    E --> F[CP-SAT Solve]
    F --> G{OPTIMAL / FEASIBLE?}
    G -->|yes| H[Phase 2: _finalize_with_changeover<br/>deterministic, exact changeover]
    G -->|no - UNKNOWN/INFEASIBLE| I[Heuristic fallback<br/>full-horizon greedy_construct]
    I --> H
    H --> J[Decode: operations, order_completions,<br/>metrics, cost_breakdown]
    J --> K[Saved to SQLite as the active schedule]
```

## 3. Replanning flow

```mermaid
flowchart TD
    A[Active schedule in SQLite] --> B[Disruption arrives<br/>breakdown/absence/delay/rework/power-cut]
    B --> C[Freeze completed + in-progress work<br/>UNLESS the disruption itself hits it]
    C --> D[Build constraint Overlay<br/>scheduler/models.py: Overlay]
    D --> E[solve_schedule with overlay<br/>frozen ops passed back as hard-fixed]
    E --> F[New schedule]
    F --> G[Diff old vs new: moved ops,<br/>order status changes, cost delta]
    G --> H[generate_owner_action<br/>data-driven recommendation]
    H --> I[Saved as new active schedule +<br/>disruption recorded in SQLite]
```

## 4. Data model / ER diagram

```mermaid
erDiagram
    MACHINE ||--o{ MAINTENANCE_WINDOW : has
    MACHINE ||--o{ BREAKDOWN : "history"
    MACHINE ||--o{ SCHEDULED_OPERATION : "runs"
    OPERATOR ||--o{ SCHEDULED_OPERATION : "assigned to"
    ORDER ||--|{ OPERATION : "routing (3-6 steps)"
    OPERATION ||--o{ SCHEDULED_OPERATION : "scheduled as"
    ORDER ||--o| ORDER_COMPLETION : "produces"
    DISRUPTION ||--o| SCHEDULE_RESULT : "triggers replan ->"

    MACHINE {
        string machine_id PK
        string machine_type
        string[] capabilities
        float hourly_cost
        float overtime_cost
        string initial_status
    }
    OPERATOR {
        string operator_id PK
        string[] skills
        string[] qualified_machines
        json roster
    }
    ORDER {
        string order_id PK
        string customer
        string customer_tier
        string part_family
        int quantity
        string due_date
        float late_penalty_per_day
    }
    OPERATION {
        string operation_id PK
        string order_id FK
        int sequence
        string operation_type
        int quantity
    }
    SCHEDULED_OPERATION {
        string operation_id FK
        string machine_id FK
        string operator_id FK
        int start_bucket
        int end_bucket
        float changeover_minutes_before
    }
    DISRUPTION {
        int id PK
        string disruption_type
        json payload
        json replan_result_json
    }
```

## 5. Deployment architecture

```mermaid
flowchart LR
    GH[GitHub Repository] --> NL[Netlify]
    GH --> RD[Render]
    NL --> FE[React static build<br/>VITE_API_BASE_URL env var]
    RD --> BE[Flask + gunicorn<br/>backend/app.py]
    BE --> ORT[OR-Tools CP-SAT<br/>in-process]
    BE --> SQL[(SQLite file<br/>on Render disk)]
    FE -->|HTTPS REST| BE
```

## 6. Three-strategy optimization flow

```mermaid
flowchart TD
    M[Same master data + same hard constraints] --> S1[Strategy: Cheapest<br/>minimize cost only]
    M --> S2[Strategy: Most On-Time<br/>minimize lateness, cost as tiebreak]
    M --> S3[Strategy: Most Robust<br/>minimize peak/grinding utilization<br/>+ priority-weighted tardiness]
    S1 --> R1[Schedule A + real metrics]
    S2 --> R2[Schedule B + real metrics]
    S3 --> R3[Schedule C + real metrics]
    R1 --> C[strategy_service.compare_strategies]
    R2 --> C
    R3 --> C
    C --> Rec[build_recommendation<br/>scored from actual on-time%, cost, utilization]
```

See [system-design.md](system-design.md) for the component-level
narrative behind each box, and
[scheduling-algorithm.md](scheduling-algorithm.md) /
[disruption-replanning.md](disruption-replanning.md) for the two flows
that matter most.
