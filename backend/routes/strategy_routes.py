from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

import db
from scheduler.solver import SchedulingError
from scheduler.objectives import STRATEGIES
from services import data_service, strategy_service
from routes._shared import error_response

logger = logging.getLogger(__name__)
strategy_bp = Blueprint("strategies", __name__, url_prefix="/api/strategies")

STRATEGY_DESCRIPTIONS = {
    "cheapest": "Minimizes total monetary cost (operating + overtime + penalties + changeovers).",
    "most_on_time": "Minimizes late orders and total tardiness, weighted by customer priority.",
    "most_robust": "Keeps spare capacity on bottleneck machines (especially grinding) so the plan can "
                   "absorb a breakdown without collapsing.",
}


@strategy_bp.get("")
def list_strategies():
    return jsonify({"success": True, "data": [
        {"strategy": s, "description": STRATEGY_DESCRIPTIONS[s]} for s in STRATEGIES
    ]})


@strategy_bp.post("/compare")
def compare():
    body = request.get_json(silent=True) or {}
    time_limit = float(body.get("time_limit_seconds", 25.0))
    machines, operators, orders, changeovers = data_service.load_all()
    try:
        comparison = strategy_service.compare_strategies(machines, operators, orders, changeovers, time_limit)
    except SchedulingError as e:
        logger.warning("Strategy comparison failed: %s", e.message)
        return error_response(e)

    # Persist each strategy's schedule as the active one for that strategy,
    # so /api/schedule?strategy=X reflects the just-compared results.
    for strat, result in comparison["full_results"].items():
        db.save_schedule(strat, result["generated_at"], result, make_active=True)
    db.save_strategy_comparison(comparison["generated_at"],
                                 {"comparison": comparison["comparison"], "recommendation": comparison["recommendation"]})

    return jsonify({"success": True, "data": {
        "generated_at": comparison["generated_at"],
        "comparison": comparison["comparison"],
        "recommendation": comparison["recommendation"],
    }})


@strategy_bp.get("/compare/latest")
def latest_comparison():
    data = db.get_latest_strategy_comparison()
    if data is None:
        return jsonify({"success": True, "data": None})
    return jsonify({"success": True, "data": data})
