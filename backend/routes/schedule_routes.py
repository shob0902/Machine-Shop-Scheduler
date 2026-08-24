from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

import db
from scheduler.solver import solve_schedule, SchedulingError
from scheduler.objectives import STRATEGIES
from services import data_service, disruption_service
from routes._shared import get_or_generate_active_schedule, error_response, validation_error

logger = logging.getLogger(__name__)
schedule_bp = Blueprint("schedule", __name__, url_prefix="/api/schedule")


@schedule_bp.get("")
def get_schedule():
    strategy = request.args.get("strategy", "cheapest")
    if strategy not in STRATEGIES:
        return validation_error(f"Unknown strategy '{strategy}'.", {"valid_strategies": list(STRATEGIES)})
    try:
        result = get_or_generate_active_schedule(strategy)
    except SchedulingError as e:
        logger.warning("Schedule generation failed: %s", e.message)
        return error_response(e)
    return jsonify({"success": True, "data": result})


@schedule_bp.post("/generate")
def generate_schedule():
    body = request.get_json(silent=True) or {}
    strategy = body.get("strategy", "cheapest")
    if strategy not in STRATEGIES:
        return validation_error(f"Unknown strategy '{strategy}'.", {"valid_strategies": list(STRATEGIES)})
    time_limit = float(body.get("time_limit_seconds", 60.0))
    regenerate_data = bool(body.get("regenerate_data", False))

    if regenerate_data:
        data_service.regenerate(num_orders=int(body.get("num_orders", 25)))
        db.reset_all()

    machines, operators, orders, changeovers = data_service.load_all()
    try:
        result = solve_schedule(machines, operators, orders, changeovers, strategy=strategy,
                                 time_limit_seconds=time_limit)
    except SchedulingError as e:
        logger.warning("Schedule generation failed: %s", e.message)
        return error_response(e)

    db.save_schedule(strategy, result["generated_at"], result, make_active=True)
    return jsonify({"success": True, "data": result})


@schedule_bp.post("/replan")
def replan_schedule():
    body = request.get_json(silent=True) or {}
    disruption_type = body.get("disruption_type")
    payload = body.get("payload")
    strategy = body.get("strategy", "cheapest")
    if not disruption_type or not isinstance(payload, dict):
        return validation_error("Request body must include 'disruption_type' and a 'payload' object.")

    previous = db.get_active_schedule(strategy)
    if previous is None:
        return validation_error("No active schedule exists yet for this strategy - call "
                                 "POST /api/schedule/generate first.")

    machines, operators, orders, changeovers = data_service.load_all()
    try:
        result = disruption_service.apply_disruption(
            disruption_type, payload, machines, operators, orders, changeovers, previous,
            now_bucket=body.get("now_bucket"), strategy=strategy,
            time_limit_seconds=float(body.get("time_limit_seconds", 45.0)),
        )
    except SchedulingError as e:
        logger.warning("Replan failed: %s", e.message)
        return error_response(e)
    except ValueError as e:
        return validation_error(str(e))

    db.save_schedule(strategy, result["generated_at"], result, make_active=True)
    disruption_service.record_disruption(disruption_type, payload, replan_result=result)
    return jsonify({"success": True, "data": result})
