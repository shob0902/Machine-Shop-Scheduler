from __future__ import annotations

from flask import Blueprint, jsonify, request

from scheduler.solver import SchedulingError
from services import data_service
from routes._shared import get_or_generate_active_schedule, error_response

order_bp = Blueprint("orders", __name__, url_prefix="/api/orders")


@order_bp.get("")
def list_orders():
    strategy = request.args.get("strategy", "cheapest")
    orders = data_service.load_orders()
    try:
        schedule = get_or_generate_active_schedule(strategy)
    except SchedulingError as e:
        return error_response(e)

    completions = {c["order_id"]: c for c in schedule["order_completions"]}
    ops_by_order: dict = {}
    for op in schedule["operations"]:
        ops_by_order.setdefault(op["order_id"], []).append(op)

    out = []
    for o in orders:
        comp = completions.get(o["order_id"])
        out.append({
            "order_id": o["order_id"], "customer": o["customer"], "customer_tier": o["customer_tier"],
            "part_family": o["part_family"], "quantity": o["quantity"], "due_date": o["due_date"],
            "release_date": o["release_date"], "material_available_date": o["material_available_date"],
            "revenue_priority": o["revenue_priority"], "late_penalty_per_day": o["late_penalty_per_day"],
            "order_value": o["order_value"], "num_operations": len(o["routing"]),
            "promised_completion": comp["promised_completion"] if comp else None,
            "status": comp["status"] if comp else "UNSCHEDULED",
            "tardiness_hours": comp["tardiness_hours"] if comp else 0,
            "scheduled_operations": len(ops_by_order.get(o["order_id"], [])),
        })
    return jsonify({"success": True, "data": out})


@order_bp.get("/<order_id>")
def get_order(order_id: str):
    strategy = request.args.get("strategy", "cheapest")
    orders = data_service.load_orders()
    order = next((o for o in orders if o["order_id"] == order_id), None)
    if order is None:
        return {"success": False, "error": f"Order '{order_id}' not found."}, 404
    try:
        schedule = get_or_generate_active_schedule(strategy)
    except SchedulingError as e:
        return error_response(e)
    completion = next((c for c in schedule["order_completions"] if c["order_id"] == order_id), None)
    operations = [op for op in schedule["operations"] if op["order_id"] == order_id]
    return jsonify({"success": True, "data": {"order": order, "completion": completion, "operations": operations}})
