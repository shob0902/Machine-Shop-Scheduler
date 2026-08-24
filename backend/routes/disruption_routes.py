from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

import db
from scheduler.solver import SchedulingError
from services import data_service, disruption_service
from routes._shared import error_response, validation_error

logger = logging.getLogger(__name__)
disruption_bp = Blueprint("disruptions", __name__, url_prefix="/api/disruptions")

REQUIRED_FIELDS = {
    "machine_breakdown": ["machine_id", "start_time", "duration_minutes"],
    "operator_absence": ["operator_id", "day_index", "shift"],
    "material_delay": ["order_id", "new_material_available_time"],
    "rework": ["order_id", "quantity"],
    "power_cut": ["day_index", "shift", "duration_minutes"],
}


@disruption_bp.get("")
def list_disruptions():
    return jsonify({"success": True, "data": db.list_disruptions()})


def _validate_references(disruption_type: str, payload: dict, machines: list, operators: list, orders: list):
    """Section 33: an invalid machine/operator/order ID must produce a
    clear validation error, not be silently ignored or crash the solve."""
    machine_ids = {m["machine_id"] for m in machines}
    operator_ids = {o["operator_id"] for o in operators}
    order_ids = {o["order_id"] for o in orders}

    if disruption_type == "machine_breakdown" and payload.get("machine_id") not in machine_ids:
        return validation_error(f"Unknown machine_id '{payload.get('machine_id')}'.",
                                 {"valid_machine_ids": sorted(machine_ids)})
    if disruption_type == "operator_absence" and payload.get("operator_id") not in operator_ids:
        return validation_error(f"Unknown operator_id '{payload.get('operator_id')}'.",
                                 {"valid_operator_ids": sorted(operator_ids)})
    if disruption_type in ("material_delay", "rework") and payload.get("order_id") not in order_ids:
        return validation_error(f"Unknown order_id '{payload.get('order_id')}'.",
                                 {"valid_order_ids": sorted(order_ids)})
    return None


def _apply(disruption_type: str, payload: dict, strategy: str, time_limit_seconds: float):
    missing = [f for f in REQUIRED_FIELDS.get(disruption_type, []) if f not in payload]
    if missing:
        return validation_error(f"Missing required field(s) for '{disruption_type}': {', '.join(missing)}.")

    previous = db.get_active_schedule(strategy)
    if previous is None:
        return validation_error("No active schedule exists yet for this strategy - call "
                                 "POST /api/schedule/generate first.")

    machines, operators, orders, changeovers = data_service.load_all()

    ref_error = _validate_references(disruption_type, payload, machines, operators, orders)
    if ref_error:
        return ref_error

    try:
        result = disruption_service.apply_disruption(
            disruption_type, payload, machines, operators, orders, changeovers, previous,
            strategy=strategy, time_limit_seconds=time_limit_seconds,
        )
    except SchedulingError as e:
        logger.warning("Disruption '%s' could not be applied: %s", disruption_type, e.message)
        return error_response(e)
    except ValueError as e:
        return validation_error(str(e))

    db.save_schedule(strategy, result["generated_at"], result, make_active=True)
    disruption_service.record_disruption(disruption_type, payload, replan_result=result)
    return jsonify({"success": True, "data": result})


@disruption_bp.post("")
def create_disruption():
    body = request.get_json(silent=True) or {}
    disruption_type = body.get("disruption_type")
    payload = body.get("payload", {})
    strategy = body.get("strategy", "cheapest")
    if disruption_type not in REQUIRED_FIELDS:
        return validation_error(f"'disruption_type' must be one of {list(REQUIRED_FIELDS)}.")
    return _apply(disruption_type, payload, strategy, float(body.get("time_limit_seconds", 45.0)))


def _typed_endpoint(disruption_type: str):
    body = request.get_json(silent=True) or {}
    strategy = body.pop("strategy", "cheapest")
    time_limit = float(body.pop("time_limit_seconds", 45.0))
    return _apply(disruption_type, body, strategy, time_limit)


@disruption_bp.post("/breakdown")
def breakdown():
    return _typed_endpoint("machine_breakdown")


@disruption_bp.post("/operator-absence")
def operator_absence():
    return _typed_endpoint("operator_absence")


@disruption_bp.post("/material-delay")
def material_delay():
    return _typed_endpoint("material_delay")


@disruption_bp.post("/rework")
def rework():
    return _typed_endpoint("rework")


@disruption_bp.post("/power-cut")
def power_cut():
    return _typed_endpoint("power_cut")
