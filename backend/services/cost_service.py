"""
Cost calculation helpers.

The core per-operation cost breakdown (operating / overtime / penalty /
changeover) is computed directly from a solved schedule inside
scheduler/solver.py (`_decode_cost_breakdown`) because it needs the exact
realized machine+operator assignment of every operation. This module adds
the pieces that sit ON TOP of a schedule rather than inside it: formatting a
breakdown for the frontend, and pricing the optional diesel-generator
power-cut scenario.
"""
from __future__ import annotations

from config import GENERATOR_COST_MULTIPLIER


def with_percentages(cost_breakdown: dict) -> dict:
    total = cost_breakdown.get("total_cost", 0) or 1
    components = ["operating_cost", "overtime_cost", "penalty_cost", "changeover_cost", "other_disruption_cost"]
    out = dict(cost_breakdown)
    out["breakdown_pct"] = {
        c: round(100 * cost_breakdown.get(c, 0) / total, 1) for c in components
    }
    return out


def price_power_cut(operations: list, machine_infos_hourly_cost: dict, day_index: int, shift: int,
                     duration_minutes: int, use_generator: bool) -> dict:
    """
    a power cut can either be absorbed by losing the shift
    (operations in that window cannot run -> they become disruption-affected
    operations for the replanner to move) or by running a diesel generator at
    GENERATOR_COST_MULTIPLIER x the normal electricity-linked machine cost.
    This function only PRICES the generator option for the affected window;
    the replanner is what actually decides whether operations move.
    """
    affected = [op for op in operations if op["day_index"] == day_index and op["shift"] in (shift,)]
    if not use_generator:
        return {
            "option": "lose_shift", "affected_operations": len(affected),
            "generator_cost": 0.0,
            "note": f"{len(affected)} operation(s) in day {day_index} shift {shift} must be replanned "
                    f"to another shift/machine.",
        }
    normal_cost = 0.0
    for op in affected:
        rate = machine_infos_hourly_cost.get(op["machine_id"], 0)
        hours = (op["end_bucket"] - op["start_bucket"]) / 4  # 15-min buckets -> hours (fallback if 30-min, still ok as an estimate)
        normal_cost += rate * hours
    generator_cost = normal_cost * GENERATOR_COST_MULTIPLIER
    return {
        "option": "run_generator", "affected_operations": len(affected),
        "normal_cost": round(normal_cost, 2), "generator_cost": round(generator_cost, 2),
        "extra_cost": round(generator_cost - normal_cost, 2),
        "note": f"Running the generator for day {day_index} shift {shift} keeps {len(affected)} "
                f"operation(s) on schedule at {GENERATOR_COST_MULTIPLIER}x electricity cost.",
    }
