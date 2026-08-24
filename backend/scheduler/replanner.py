"""
Disruption replanning engine (Section 24-26 - "the heart of the assignment").

Given the schedule currently on file and a disruption, this module:
  1. Freezes completed and in-progress operations (unless the disruption
     itself interrupts an in-progress operation, e.g. its machine just broke
     down mid-job - see `_is_disrupted`).
  2. Applies the disruption as a constraint overlay (extra blocked machine
     time, operator absence, a later material date, or an injected rework
     batch) via scheduler.models.Overlay.
  3. Re-solves ONLY the non-frozen future work with scheduler.solve_schedule,
     which is what "does not regenerate an unrelated schedule from scratch"
     means in practice here: every already-started or completed operation is
     passed back in as a hard-fixed assignment, so the optimizer can only
     move what has not happened yet.
  4. Diffs the old and new schedules operation-by-operation and order-by-
     order, and prices the difference (Section 20/26 - disruption cost).
"""
from __future__ import annotations

from typing import Optional

from scheduler.models import Overlay
from scheduler.solver import solve_schedule, SchedulingError


def _is_disrupted(op: dict, overlay: Overlay) -> bool:
    """True if an in-progress operation is caught by the new disruption and
    must be un-frozen (its remaining/actual progress is not modeled at
    sub-operation granularity - Section 25's "preserve where possible" is
    honored for every operation the disruption does NOT directly hit)."""
    for (bs, be) in overlay.extra_blocked_ranges.get(op["machine_id"], []):
        if op["start_bucket"] < be and bs < op["end_bucket"]:
            return True
    for (day, shift) in overlay.operator_extra_absences.get(op["operator_id"], []):
        if op["day_index"] == day and op["shift"] == shift:
            return True
    if op["order_id"] in overlay.material_overrides:
        return True
    return False


def replan(machines: list, operators: list, orders: list, changeovers: dict,
           previous_result: dict, now_bucket: int, overlay: Overlay, strategy: str = "cheapest",
           time_limit_seconds: float = 45.0) -> dict:
    previous_ops = previous_result["operations"]

    frozen_ops = []
    for op in previous_ops:
        completed = op["end_bucket"] <= now_bucket
        in_progress = op["start_bucket"] <= now_bucket < op["end_bucket"]
        if completed or (in_progress and not _is_disrupted(op, overlay)):
            frozen_ops.append(op)

    overlay.frozen_task_ids = {op["operation_id"] for op in frozen_ops}
    overlay.task_assignments = {
        op["operation_id"]: {
            "machine_id": op["machine_id"], "operator_id": op["operator_id"],
            "start_bucket": op["start_bucket"], "end_bucket": op["end_bucket"],
        } for op in frozen_ops
    }
    overlay.min_start_bucket = max(overlay.min_start_bucket, now_bucket)

    new_result = solve_schedule(machines, operators, orders, changeovers, strategy=strategy,
                                 overlay=overlay, time_limit_seconds=time_limit_seconds)

    new_result["comparison"] = _compare(previous_result, new_result, now_bucket, overlay)
    new_result["frozen_operation_count"] = len(frozen_ops)
    new_result["reoptimized_operation_count"] = len(new_result["operations"]) - len(frozen_ops)
    return new_result


def _compare(previous_result: dict, new_result: dict, now_bucket: int, overlay: Overlay) -> dict:
    old_ops = {op["operation_id"]: op for op in previous_result["operations"]}
    new_ops = {op["operation_id"]: op for op in new_result["operations"]}
    old_completions = {c["order_id"]: c for c in previous_result["order_completions"]}
    new_completions = {c["order_id"]: c for c in new_result["order_completions"]}

    moved_operations = []
    for tid, new_op in new_ops.items():
        old_op = old_ops.get(tid)
        if old_op is None:
            moved_operations.append({
                "operation_id": tid, "order_id": new_op["order_id"], "change": "new_operation_added",
                "new_machine": new_op["machine_id"], "new_operator": new_op["operator_id"],
                "new_start_time": new_op["start_time"],
            })
            continue
        if old_op["start_bucket"] == new_op["start_bucket"] and old_op["machine_id"] == new_op["machine_id"] \
                and old_op["operator_id"] == new_op["operator_id"]:
            continue
        moved_operations.append({
            "operation_id": tid, "order_id": new_op["order_id"],
            "old_machine": old_op["machine_id"], "new_machine": new_op["machine_id"],
            "changed_machine": old_op["machine_id"] != new_op["machine_id"],
            "old_operator": old_op["operator_id"], "new_operator": new_op["operator_id"],
            "changed_operator": old_op["operator_id"] != new_op["operator_id"],
            "old_start_time": old_op["start_time"], "new_start_time": new_op["start_time"],
            "delta_hours": round((new_op["start_bucket"] - old_op["start_bucket"]) / 4, 2),
        })

    order_changes = []
    for order_id, new_c in new_completions.items():
        old_c = old_completions.get(order_id)
        if old_c is None:
            continue
        moved = old_c["promised_completion"] != new_c["promised_completion"]
        order_changes.append({
            "order_id": order_id, "customer": new_c["customer"], "customer_tier": new_c["customer_tier"],
            "old_completion": old_c["promised_completion"], "new_completion": new_c["promised_completion"],
            "old_status": old_c["status"], "new_status": new_c["status"],
            "moved": moved, "newly_late": old_c["status"] != "LATE" and new_c["status"] == "LATE",
            "delta_hours": round(new_c["tardiness_hours"] - old_c["tardiness_hours"], 2),
        })

    old_cost = previous_result["cost_breakdown"]
    new_cost = new_result["cost_breakdown"]
    cost_delta = {k: round(new_cost.get(k, 0) - old_cost.get(k, 0), 2)
                  for k in ("operating_cost", "overtime_cost", "penalty_cost", "changeover_cost", "total_cost")}

    old_overtime_ops = {tid for tid, op in old_ops.items() if op["is_overtime"]}
    new_overtime_ops = {tid for tid, op in new_ops.items() if op["is_overtime"]}
    newly_overtime = new_overtime_ops - old_overtime_ops

    return {
        "now_bucket": now_bucket,
        "moved_operations": moved_operations,
        "moved_operation_count": len(moved_operations),
        "order_changes": order_changes,
        "newly_late_orders": [c["order_id"] for c in order_changes if c["newly_late"]],
        "new_overtime_operations": sorted(newly_overtime),
        "cost_delta": cost_delta,
        "disruption_cost": cost_delta["total_cost"],
        "wasted_changeover_minutes_delta": round(
            new_cost.get("wasted_changeover_minutes", 0) - old_cost.get("wasted_changeover_minutes", 0), 1),
    }
