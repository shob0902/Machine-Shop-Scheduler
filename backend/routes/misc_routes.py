from __future__ import annotations

from flask import Blueprint, jsonify, request

import db
from scheduler.solver import SchedulingError
from services import data_service, cost_service, metrics_service
from routes._shared import get_or_generate_active_schedule, error_response

misc_bp = Blueprint("misc", __name__, url_prefix="/api")


@misc_bp.get("/health")
def health():
    return jsonify({"success": True, "status": "ok", "service": "machine-shop-scheduler-backend"})


@misc_bp.get("/operators")
def list_operators():
    return jsonify({"success": True, "data": data_service.load_operators()})


@misc_bp.get("/dashboard")
def dashboard():
    strategy = request.args.get("strategy", "cheapest")
    machines = data_service.load_machines()
    try:
        schedule = get_or_generate_active_schedule(strategy)
    except SchedulingError as e:
        return error_response(e)
    recent = db.list_disruptions(limit=10)
    return jsonify({"success": True, "data": metrics_service.build_dashboard(schedule, machines, recent)})


@misc_bp.get("/costs")
def costs():
    strategy = request.args.get("strategy", "cheapest")
    try:
        schedule = get_or_generate_active_schedule(strategy)
    except SchedulingError as e:
        return error_response(e)
    return jsonify({"success": True, "data": cost_service.with_percentages(schedule["cost_breakdown"])})


@misc_bp.get("/metrics")
def metrics():
    strategy = request.args.get("strategy", "cheapest")
    try:
        schedule = get_or_generate_active_schedule(strategy)
    except SchedulingError as e:
        return error_response(e)
    return jsonify({"success": True, "data": schedule["metrics"]})
