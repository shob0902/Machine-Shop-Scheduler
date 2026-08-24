"""Small helpers shared across route blueprints."""
from __future__ import annotations

from datetime import datetime

import db
from scheduler.solver import SchedulingError
from services import data_service


def get_or_generate_active_schedule(strategy: str = "cheapest", time_limit_seconds: float = 60.0) -> dict:
    existing = db.get_active_schedule(strategy)
    if existing:
        return existing
    from scheduler.solver import solve_schedule
    machines, operators, orders, changeovers = data_service.load_all()
    result = solve_schedule(machines, operators, orders, changeovers, strategy=strategy,
                             time_limit_seconds=time_limit_seconds)
    db.save_schedule(strategy, result["generated_at"], result, make_active=True)
    return result


def error_response(exc: SchedulingError, status_code: int = 422):
    return exc.to_dict(), status_code


def validation_error(message: str, details: dict | None = None):
    return {"success": False, "error": message, "suggestion": "Check the request payload against the API docs "
            "in README.md.", "details": details or {}}, 400
