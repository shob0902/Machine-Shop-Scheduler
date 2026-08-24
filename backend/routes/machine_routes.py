from __future__ import annotations

from flask import Blueprint, jsonify, request

from scheduler.solver import SchedulingError
from services import data_service
from routes._shared import get_or_generate_active_schedule, error_response

machine_bp = Blueprint("machines", __name__, url_prefix="/api/machines")


def _reliability(machine: dict) -> dict:
    history = machine.get("breakdown_history", [])
    if not history:
        return {"breakdown_count": 0, "total_downtime_minutes": 0, "avg_downtime_minutes": 0.0, "mtbf_hours": None}
    total = sum(b["duration_minutes"] for b in history)
    count = len(history)
    observation_hours = 180 * 24
    return {
        "breakdown_count": count,
        "total_downtime_minutes": total,
        "avg_downtime_minutes": round(total / count, 1),
        "mtbf_hours": round((observation_hours - total / 60) / count, 1),
    }


@machine_bp.get("")
def list_machines():
    strategy = request.args.get("strategy", "cheapest")
    machines = data_service.load_machines()
    try:
        schedule = get_or_generate_active_schedule(strategy)
    except SchedulingError as e:
        return error_response(e)

    util = schedule["metrics"]["machine_utilization"]
    ops_by_machine: dict = {}
    for op in schedule["operations"]:
        ops_by_machine.setdefault(op["machine_id"], []).append(op)

    out = []
    for m in machines:
        mops = sorted(ops_by_machine.get(m["machine_id"], []), key=lambda o: o["start_bucket"])
        current_op = mops[0] if mops else None
        next_op = mops[1] if len(mops) > 1 else None
        out.append({
            "machine_id": m["machine_id"], "machine_name": m["machine_name"], "machine_type": m["machine_type"],
            "capabilities": m["capabilities"], "hourly_cost": m["hourly_cost"], "overtime_cost": m["overtime_cost"],
            "status": m["initial_status"], "maintenance_windows": m["maintenance_windows"],
            "utilization": util.get(m["machine_id"], {}),
            "current_operation": current_op, "next_operation": next_op,
            "scheduled_operation_count": len(mops),
            "reliability": _reliability(m),
        })
    return jsonify({"success": True, "data": out})


@machine_bp.get("/<machine_id>")
def get_machine(machine_id: str):
    strategy = request.args.get("strategy", "cheapest")
    machines = data_service.load_machines()
    machine = next((m for m in machines if m["machine_id"] == machine_id), None)
    if machine is None:
        return {"success": False, "error": f"Machine '{machine_id}' not found."}, 404
    try:
        schedule = get_or_generate_active_schedule(strategy)
    except SchedulingError as e:
        return error_response(e)
    ops = sorted([op for op in schedule["operations"] if op["machine_id"] == machine_id],
                 key=lambda o: o["start_bucket"])
    util = schedule["metrics"]["machine_utilization"].get(machine_id, {})
    return jsonify({"success": True, "data": {
        "machine": machine, "utilization": util, "operations": ops, "reliability": _reliability(machine),
    }})
