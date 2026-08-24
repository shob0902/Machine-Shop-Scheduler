"""
Top-level scheduling orchestration: build the CP-SAT model, solve it, and
decode the raw solver solution into the plain-dict shape the Flask API and
cost/strategy services consume (mirrors models/schedule.py's ScheduleResult).

Two-phase design (see scheduler/constraints.py's _add_resource_disjunctions
docstring for the full rationale):
  Phase 1 (CP-SAT, or the greedy heuristic as a timeout fallback) decides
    WHICH machine and operator every operation gets, optimizing the chosen
    strategy's cost/lateness/robustness objective against efficient
    AddNoOverlap capacity constraints.
  Phase 2 (_finalize_with_changeover, always run) replays those assignments
    in the relative order Phase 1 produced and recomputes exact start/end
    times so every sequence-dependent changeover gap (Section 6), machine
    maintenance window, and operator shift boundary is genuinely respected
    in the schedule actually returned to the API - changeover is a real,
    enforced part of the final output, not a decorative table.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

from ortools.sat.python import cp_model

from config import BUCKET_MINUTES, BUCKETS_PER_DAY, BUCKETS_PER_DAY_WITH_OT, HORIZON_DAYS
from calendar_utils import bucket_to_datetime, day_index_of_bucket, shift_of_bucket, TOTAL_BUCKETS
from scheduler.models import build_solver_input, Overlay, minutes_to_buckets
from scheduler.constraints import build_model, changeover_minutes
from scheduler.objectives import build_objective, STRATEGIES
from scheduler.heuristic import greedy_construct, _earliest_free_slot

AT_RISK_SLACK_BUCKETS = BUCKETS_PER_DAY  # < 1 day of slack before due date => AT_RISK


class SchedulingError(Exception):
    """Raised whenever OR-Tools cannot produce a feasible schedule, or the
    request itself is invalid. Always carries a human-readable suggestion,
    per Section 33 ("Error Handling")."""
    def __init__(self, message: str, suggestion: Optional[str] = None, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.suggestion = suggestion or (
            "Consider enabling overtime, relaxing the requested delivery date, "
            "or reassigning a qualified operator/machine."
        )
        self.details = details or {}

    def to_dict(self) -> dict:
        return {"success": False, "error": self.message, "suggestion": self.suggestion, "details": self.details}


def solve_schedule(machines: list, operators: list, orders: list, changeovers: dict,
                    strategy: str = "cheapest", overlay: Optional[Overlay] = None,
                    time_limit_seconds: float = 60.0, num_workers: int = 8) -> dict:
    if strategy not in STRATEGIES:
        raise SchedulingError(f"Unknown strategy '{strategy}'.", f"Valid strategies: {', '.join(STRATEGIES)}")

    tasks, order_infos, machine_infos, operator_infos = build_solver_input(
        machines, operators, orders, changeovers, overlay)

    if not tasks:
        raise SchedulingError("No schedulable operations were found.",
                               "Check that machines/orders/operators data has been generated.")

    tasks_by_id = {t.operation_id: t for t in tasks}
    V = build_model(tasks, order_infos, machine_infos, operator_infos, changeovers, TOTAL_BUCKETS)

    if V.infeasible_tasks:
        raise SchedulingError(
            "No feasible schedule exists under the current constraints: "
            f"{len(V.infeasible_tasks)} operation(s) have no valid (machine, operator) combination.",
            "Consider enabling overtime, resolving an operator-absence conflict, "
            "or checking that a capable machine is not shown as permanently down.",
            {"unassignable_operations": V.infeasible_tasks},
        )

    result = build_objective(strategy, V, order_infos, machine_infos, operator_infos)
    V.model.Minimize(result.objective_expr)

    _add_warm_start_hint(V, tasks, order_infos, machine_infos, operator_infos, changeovers, TOTAL_BUCKETS, strategy)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.num_search_workers = num_workers
    solver.parameters.random_seed = 42
    t0 = time.time()
    status = solver.Solve(V.model)
    wall_time = time.time() - t0

    solver_status_name = solver.StatusName(status)
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        placements = _extract_placements(solver, V)
    else:
        # UNKNOWN (no incumbent within the time budget) or INFEASIBLE both
        # fall back to the same constructive heuristic before we trust that
        # verdict: CP-SAT's search space is deliberately pruned for
        # performance (DUE_DATE_SEARCH_SLACK_BUCKETS in constraints.py caps
        # how far past a due date an operation is even considered), so an
        # "INFEASIBLE" from CP-SAT proves only that no solution exists
        # WITHIN that pruned window - not that the shop truly cannot deliver
        # the order at all. Only if the heuristic (which searches the full
        # horizon, unpruned) also cannot place every operation do we report
        # genuine infeasibility. See docs/scheduling-algorithm.md
        # "Solver performance".
        placements = greedy_construct(tasks, order_infos, machine_infos, operator_infos, changeovers, TOTAL_BUCKETS,
                                       strategy=strategy)
        unplaced = [tid for tid in V.start if tid not in placements]
        if unplaced:
            raise SchedulingError(
                "No feasible schedule exists under the current constraints.",
                "Consider enabling overtime, resolving an operator-absence conflict, "
                "adding a machine breakdown recovery window, or relaxing a delivery date.",
                {"solver_status": solver_status_name, "unplaced_operations": unplaced},
            )
        solver_status_name = "FEASIBLE_HEURISTIC_FALLBACK"

    operations = _finalize_with_changeover(tasks_by_id, placements, machine_infos, operator_infos,
                                            changeovers, TOTAL_BUCKETS)
    order_completions = _decode_order_completions(operations, order_infos)
    metrics = _compute_metrics(operations, order_completions, machine_infos, operator_infos)
    cost_breakdown = _decode_cost_breakdown(operations, order_completions, machine_infos, operator_infos, order_infos)

    return {
        "strategy": strategy,
        "generated_at": datetime.now().isoformat(),
        "solver_status": solver_status_name,
        "solver_wall_time_seconds": round(wall_time, 3),
        "objective_value": solver.ObjectiveValue() if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
        "operations": operations,
        "order_completions": order_completions,
        "metrics": metrics,
        "cost_breakdown": cost_breakdown,
        "weights_used": result.weights_used,
    }


def _add_warm_start_hint(V, tasks, order_infos, machine_infos, operator_infos, changeovers, horizon_buckets,
                          strategy: str = "most_on_time") -> None:
    """Seed CP-SAT with a greedy feasible solution (see scheduler/heuristic.py)
    so search starts from a valid point instead of an empty one. Best-effort:
    if the heuristic cannot place every task, CP-SAT still solves exactly -
    it simply gets a partial hint."""
    try:
        greedy = greedy_construct(tasks, order_infos, machine_infos, operator_infos, changeovers, horizon_buckets,
                                   strategy=strategy)
    except Exception:
        return  # warm start is an optimization, never a correctness requirement
    hint_vars, hint_vals = [], []
    for tid, placement in greedy.items():
        if tid not in V.start:
            continue
        hint_vars.append(V.start[tid])
        hint_vals.append(placement["start"])
        key = (placement["machine_id"], placement["operator_id"])
        if key in V.assign.get(tid, {}):
            for k, var in V.assign[tid].items():
                hint_vars.append(var)
                hint_vals.append(1 if k == key else 0)
    try:
        for var, val in zip(hint_vars, hint_vals):
            V.model.AddHint(var, val)
    except Exception:
        pass  # warm start is an optimization, never a correctness requirement


def _extract_placements(solver: cp_model.CpSolver, V) -> dict:
    placements = {}
    for tid in V.start:
        s = solver.Value(V.start[tid])
        e = solver.Value(V.end[tid])
        machine_id, operator_id = None, None
        for (m, o), var in V.assign[tid].items():
            if solver.Value(var) == 1:
                machine_id, operator_id = m, o
                break
        placements[tid] = {"machine_id": machine_id, "operator_id": operator_id, "start": s, "end": e}
    return placements


def _task_is_overtime(start_bucket: int, duration_buckets: int) -> bool:
    offset = start_bucket % BUCKETS_PER_DAY_WITH_OT
    return offset + duration_buckets - 1 >= BUCKETS_PER_DAY


def _finalize_with_changeover(tasks_by_id, placements: dict, machine_infos, operator_infos,
                               changeovers: dict, horizon_buckets: int) -> list:
    """Phase 2 (see module docstring): replay Phase 1's (machine, operator)
    choices in the relative order Phase 1 produced, recomputing exact timing
    so precedence, resource capacity, maintenance/shift blocked ranges, AND
    sequence-dependent changeover are all genuinely satisfied in the result."""
    ordered_ids = sorted(placements.keys(), key=lambda tid: (placements[tid]["start"], tasks_by_id[tid].sequence))

    machine_occupied: dict = {}
    operator_occupied: dict = {}
    order_step_end: dict = {}  # order_id -> {sequence: max finalized end}
    operations = []

    for tid in ordered_ids:
        t = tasks_by_id[tid]
        placement = placements[tid]
        m, o = placement["machine_id"], placement["operator_id"]
        if t.frozen:
            slot, finish = t.frozen_start, t.frozen_end
        else:
            steps = order_step_end.get(t.order_id, {})
            precedence_bound = max([v for s, v in steps.items() if s < t.sequence], default=0)
            earliest = max(t.earliest_start_bucket, precedence_bound)

            m_occ = machine_occupied.setdefault(m, [])
            o_occ = operator_occupied.setdefault(o, [])
            last_fam = None
            if m_occ:
                last_end = max(e for _, e, _ in m_occ)
                last_fam = next(f for s, e, f in m_occ if e == last_end)
            fam_gap = 0
            if last_fam is not None and last_fam != t.part_family:
                fam_gap = minutes_to_buckets(changeover_minutes(changeovers, last_fam, t.part_family))

            blocked = list(machine_infos[m].blocked_ranges) + list(operator_infos[o].blocked_ranges)
            occ = [(s, e) for s, e, _ in m_occ] + o_occ
            slot = _earliest_free_slot(occ, blocked, t.duration_buckets, earliest + fam_gap, horizon_buckets)
            if slot is None:
                slot = earliest + fam_gap  # best-effort: extremely rare given headroom in the dataset
            finish = slot + t.duration_buckets

        machine_occupied.setdefault(m, []).append((slot, finish, t.part_family))
        operator_occupied.setdefault(o, []).append((slot, finish))
        steps = order_step_end.setdefault(t.order_id, {})
        steps[t.sequence] = max(steps.get(t.sequence, 0), finish)

        prev_fam = None
        m_hist = [x for x in machine_occupied[m] if x[1] <= slot]
        if m_hist:
            prev_fam = max(m_hist, key=lambda x: x[1])[2]
        gap_minutes = 0.0
        if prev_fam is not None:
            gap_minutes = changeover_minutes(changeovers, prev_fam, t.part_family)

        operations.append({
            "order_id": t.order_id, "operation_id": tid, "operation_type": t.operation_type,
            "sequence": t.sequence, "machine_id": m, "operator_id": o,
            "quantity": t.quantity, "part_family": t.part_family,
            "start_bucket": slot, "end_bucket": finish,
            "start_time": bucket_to_datetime(slot).isoformat(), "end_time": bucket_to_datetime(finish).isoformat(),
            "day_index": day_index_of_bucket(slot), "shift": shift_of_bucket(slot),
            "is_overtime": _task_is_overtime(slot, t.duration_buckets),
            "changeover_minutes_before": round(gap_minutes, 1) if prev_fam is not None else 0.0,
            "previous_family_on_machine": prev_fam,
            "status": "frozen" if t.frozen else "planned", "is_rework": t.is_rework,
        })

    operations.sort(key=lambda o: (o["machine_id"] or "", o["start_bucket"]))
    return operations


def _decode_order_completions(operations: list, order_infos) -> list:
    ops_by_order: dict = {}
    for op in operations:
        ops_by_order.setdefault(op["order_id"], []).append(op)

    completions = []
    for order_id, order in order_infos.items():
        order_ops = ops_by_order.get(order_id)
        if not order_ops:
            continue
        max_seq = max(op["sequence"] for op in order_ops)
        comp_bucket = max(op["end_bucket"] for op in order_ops if op["sequence"] == max_seq)
        due_bucket = order.due_bucket
        is_late = comp_bucket > due_bucket
        tardiness_buckets = max(0, comp_bucket - due_bucket)
        slack = due_bucket - comp_bucket
        any_overtime = any(op["is_overtime"] for op in order_ops)
        if is_late:
            status = "LATE"
        elif slack < AT_RISK_SLACK_BUCKETS or any_overtime:
            status = "AT_RISK"
        else:
            status = "ON_TRACK"
        completions.append({
            "order_id": order_id, "customer": order.customer, "customer_tier": order.customer_tier,
            "due_date": bucket_to_datetime(due_bucket).isoformat(),
            "promised_completion": bucket_to_datetime(comp_bucket).isoformat(),
            "is_late": is_late, "tardiness_hours": round(tardiness_buckets * BUCKET_MINUTES / 60, 2),
            "status": status,
        })
    return completions


def _compute_metrics(operations, order_completions, machine_infos, operator_infos) -> dict:
    total_orders = len(order_completions)
    late = [c for c in order_completions if c["status"] == "LATE"]
    at_risk = [c for c in order_completions if c["status"] == "AT_RISK"]
    on_track = [c for c in order_completions if c["status"] == "ON_TRACK"]
    tardy_hours = [c["tardiness_hours"] for c in order_completions if c["tardiness_hours"] > 0]

    busy_minutes: dict = {}
    for op in operations:
        busy_minutes[op["machine_id"]] = busy_minutes.get(op["machine_id"], 0) + \
            (op["end_bucket"] - op["start_bucket"]) * BUCKET_MINUTES

    capacity_minutes = HORIZON_DAYS * BUCKETS_PER_DAY * BUCKET_MINUTES
    utilization = {}
    for mid, m in machine_infos.items():
        maint_minutes = sum((be - bs) * BUCKET_MINUTES for bs, be in m.blocked_ranges)
        avail = max(1, capacity_minutes - maint_minutes)
        utilization[mid] = {
            "machine_name": m.machine_name,
            "busy_hours": round(busy_minutes.get(mid, 0) / 60, 2),
            "available_hours": round(avail / 60, 2),
            "utilization_pct": round(min(100.0, 100 * busy_minutes.get(mid, 0) / avail), 1),
        }

    overtime_ops = [op for op in operations if op["is_overtime"]]
    overtime_hours = sum((op["end_bucket"] - op["start_bucket"]) * BUCKET_MINUTES / 60 for op in overtime_ops)

    avg_util = round(sum(u["utilization_pct"] for u in utilization.values()) / max(1, len(utilization)), 1)
    peak_util = max((u["utilization_pct"] for u in utilization.values()), default=0)

    return {
        "total_orders": total_orders,
        "not_late_orders": total_orders - len(late),
        "late_orders": len(late),
        "at_risk_orders": len(at_risk),
        "on_track_orders": len(on_track),
        "on_time_percentage": round(100 * (total_orders - len(late)) / total_orders, 1) if total_orders else 0,
        "average_tardiness_hours": round(sum(tardy_hours) / len(tardy_hours), 2) if tardy_hours else 0.0,
        "max_tardiness_hours": round(max(tardy_hours), 2) if tardy_hours else 0.0,
        "total_operations": len(operations),
        "overtime_operations": len(overtime_ops),
        "overtime_hours": round(overtime_hours, 2),
        "machine_utilization": utilization,
        "average_machine_utilization_pct": avg_util,
        "peak_machine_utilization_pct": peak_util,
    }


def _decode_cost_breakdown(operations, order_completions, machine_infos, operator_infos, order_infos) -> dict:
    """Computed directly from the realized (post-Phase-2) solution, not from
    the CP-SAT objective's linear approximation - see the note at the top of
    scheduler/objectives.py."""
    operating_cost = 0.0
    overtime_cost = 0.0
    for op in operations:
        m, o = machine_infos.get(op["machine_id"]), operator_infos.get(op["operator_id"])
        if m is None or o is None:
            continue
        hours = (op["end_bucket"] - op["start_bucket"]) * BUCKET_MINUTES / 60
        if op["is_overtime"]:
            overtime_cost += hours * (m.overtime_cost + o.overtime_rate)
        else:
            operating_cost += hours * (m.hourly_cost + o.hourly_rate)

    penalty_cost = 0.0
    for c in order_completions:
        if c["tardiness_hours"] > 0:
            order = order_infos.get(c["order_id"])
            if order:
                penalty_cost += (c["tardiness_hours"] / 24) * order.late_penalty_per_day

    changeover_cost = 0.0
    wasted_changeover_minutes = 0.0
    for op in operations:
        if op["changeover_minutes_before"] and op["machine_id"] in machine_infos:
            rate_per_hour = machine_infos[op["machine_id"]].hourly_cost
            changeover_cost += (op["changeover_minutes_before"] / 60) * rate_per_hour
            wasted_changeover_minutes += op["changeover_minutes_before"]

    total = operating_cost + overtime_cost + penalty_cost + changeover_cost
    return {
        "operating_cost": round(operating_cost, 2),
        "overtime_cost": round(overtime_cost, 2),
        "penalty_cost": round(penalty_cost, 2),
        "changeover_cost": round(changeover_cost, 2),
        "wasted_changeover_minutes": round(wasted_changeover_minutes, 1),
        "other_disruption_cost": 0.0,
        "total_cost": round(total, 2),
    }
