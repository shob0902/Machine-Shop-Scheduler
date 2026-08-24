"""Supervisor dashboard aggregation (Section 29 - Dashboard page)."""
from __future__ import annotations

from datetime import datetime


def build_dashboard(schedule_result: dict, machines: list, recent_disruptions: list) -> dict:
    m = schedule_result["metrics"]
    c = schedule_result["cost_breakdown"]
    completions = schedule_result["order_completions"]

    critical_alerts = []
    for comp in completions:
        if comp["status"] == "LATE":
            critical_alerts.append({
                "level": "critical", "icon": "red",
                "message": f"{comp['order_id']} ({comp['customer']}, {comp['customer_tier']}) is LATE by "
                           f"{comp['tardiness_hours']}h.",
            })
    down_machines = [mm for mm in machines if mm.get("initial_status") == "down"]
    for dm in down_machines:
        critical_alerts.append({
            "level": "critical", "icon": "black",
            "message": f"{dm['machine_name']} ({dm['machine_id']}) is currently DOWN.",
        })
    for comp in completions:
        if comp["status"] == "AT_RISK":
            critical_alerts.append({
                "level": "warning", "icon": "yellow",
                "message": f"{comp['order_id']} ({comp['customer']}) is AT RISK - little slack before the due date.",
            })

    critical_alerts.sort(key=lambda a: {"critical": 0, "warning": 1}.get(a["level"], 2))

    return {
        "generated_at": datetime.now().isoformat(),
        "strategy_in_use": schedule_result["strategy"],
        "total_orders": m["total_orders"],
        "on_time_percentage": m["on_time_percentage"],
        "late_orders": m["late_orders"],
        "at_risk_orders": m["at_risk_orders"],
        "on_track_orders": m["on_track_orders"],
        "average_machine_utilization_pct": m["average_machine_utilization_pct"],
        "peak_machine_utilization_pct": m["peak_machine_utilization_pct"],
        "overtime_hours": m["overtime_hours"],
        "total_cost": c["total_cost"],
        "cost_breakdown": c,
        "critical_alerts": critical_alerts[:10],
        "active_disruption_count": len([d for d in recent_disruptions if d.get("applied")]),
        "recent_disruptions": recent_disruptions[:5],
    }
