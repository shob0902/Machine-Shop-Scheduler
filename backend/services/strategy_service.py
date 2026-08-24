"""
Runs all three scheduling strategies (Section 21), builds the comparison
table (Section 22), and generates a recommendation (Section 23) from the
metrics those solves actually produced - never a hardcoded winner.
"""
from __future__ import annotations

from datetime import datetime

from scheduler.solver import solve_schedule
from scheduler.objectives import STRATEGIES

STRATEGY_LABELS = {
    "cheapest": "Cheapest",
    "most_on_time": "Most On-Time",
    "most_robust": "Most Robust",
}


def run_all_strategies(machines, operators, orders, changeovers, time_limit_seconds: float = 45.0) -> list[dict]:
    results = []
    for strategy in STRATEGIES:
        result = solve_schedule(machines, operators, orders, changeovers, strategy=strategy,
                                 time_limit_seconds=time_limit_seconds)
        results.append(result)
    return results


def build_comparison_row(result: dict) -> dict:
    m, c = result["metrics"], result["cost_breakdown"]
    return {
        "strategy": result["strategy"],
        "strategy_label": STRATEGY_LABELS.get(result["strategy"], result["strategy"]),
        "solver_status": result["solver_status"],
        "total_cost": c["total_cost"],
        "operating_cost": c["operating_cost"],
        "overtime_cost": c["overtime_cost"],
        "penalty_cost": c["penalty_cost"],
        "changeover_cost": c["changeover_cost"],
        "late_orders": m["late_orders"],
        "on_time_percentage": m["on_time_percentage"],
        "average_tardiness_hours": m["average_tardiness_hours"],
        "max_tardiness_hours": m["max_tardiness_hours"],
        "average_machine_utilization_pct": m["average_machine_utilization_pct"],
        "peak_machine_utilization_pct": m["peak_machine_utilization_pct"],
        "overtime_hours": m["overtime_hours"],
        "robustness_score": round(max(0.0, 100 - m["peak_machine_utilization_pct"]), 1),
    }


def build_recommendation(comparison: list[dict]) -> dict:
    if not comparison:
        return {"recommended_strategy": None, "reasons": ["No strategy results available."]}

    cheapest_cost = min(c["total_cost"] for c in comparison)
    best_on_time = max(c["on_time_percentage"] for c in comparison)

    scored = []
    for c in comparison:
        cost_penalty = (c["total_cost"] - cheapest_cost) / max(1.0, cheapest_cost)
        ontime_gap = (best_on_time - c["on_time_percentage"]) / 100.0
        robustness_bonus = (c["robustness_score"] / 100.0) * 0.3
        score = (c["on_time_percentage"] / 100.0) - cost_penalty * 0.5 - ontime_gap * 0.3 + robustness_bonus
        scored.append((score, c))
    scored.sort(key=lambda x: -x[0])
    best_score, best = scored[0]

    cheapest_row = min(comparison, key=lambda c: c["total_cost"])
    reasons = [f"{best['on_time_percentage']}% on-time delivery ({best['late_orders']} late order(s))"]
    reasons.append(f"{best['robustness_score']}% spare capacity on the busiest machine "
                    f"(peak utilization {best['peak_machine_utilization_pct']}%)")
    cost_diff = round(best["total_cost"] - cheapest_row["total_cost"], 2)
    if best["strategy"] == cheapest_row["strategy"]:
        reasons.append("also the lowest-cost of the three strategies")
    elif cost_diff > 0:
        reasons.append(f"costs {cost_diff:,.0f} more than the cheapest strategy "
                        f"({cheapest_row['strategy_label']}) for that improvement")

    return {
        "recommended_strategy": best["strategy"],
        "recommended_strategy_label": STRATEGY_LABELS.get(best["strategy"], best["strategy"]),
        "reasons": reasons,
        "scores": {c["strategy"]: round(s, 4) for s, c in scored},
        "generated_at": datetime.now().isoformat(),
    }


def compare_strategies(machines, operators, orders, changeovers, time_limit_seconds: float = 45.0) -> dict:
    results = run_all_strategies(machines, operators, orders, changeovers, time_limit_seconds)
    comparison = [build_comparison_row(r) for r in results]
    recommendation = build_recommendation(comparison)
    return {
        "generated_at": datetime.now().isoformat(),
        "comparison": comparison,
        "recommendation": recommendation,
        "full_results": {r["strategy"]: r for r in results},
    }
