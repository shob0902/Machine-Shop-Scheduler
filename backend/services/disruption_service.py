"""
Translates the five raw disruption payload types into a
scheduler.models.Overlay, drives the replanner, persists the result, and
generates the data-driven "what should the owner do right now" action
 - built from the actual before/after comparison, never a
hardcoded sentence.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import db
from calendar_utils import datetime_to_bucket, buckets_for_day_shift
from config import GENERATOR_COST_MULTIPLIER
from scheduler.models import Overlay
from scheduler.replanner import replan


def _parse_dt(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.fromisoformat(value + "T06:00:00")


def build_overlay(disruption_type: str, payload: dict) -> Overlay:
    overlay = Overlay()

    if disruption_type == "machine_breakdown":
        start_dt = _parse_dt(payload["start_time"])
        start_bucket = datetime_to_bucket(start_dt)
        from config import BUCKET_MINUTES
        import math
        duration_buckets = max(1, math.ceil(int(payload["duration_minutes"]) / BUCKET_MINUTES))
        end_bucket = start_bucket + duration_buckets
        overlay.extra_blocked_ranges.setdefault(payload["machine_id"], []).append((start_bucket, end_bucket))
        overlay.machine_status_override[payload["machine_id"]] = "down"

    elif disruption_type == "operator_absence":
        overlay.operator_extra_absences.setdefault(payload["operator_id"], []).append(
            (int(payload["day_index"]), int(payload["shift"])))

    elif disruption_type == "material_delay":
        new_bucket = datetime_to_bucket(_parse_dt(payload["new_material_available_time"]))
        overlay.material_overrides[payload["order_id"]] = new_bucket

    elif disruption_type == "rework":
        overlay.rework_events.append({
            "order_id": payload["order_id"],
            "operation_id": payload.get("operation_id"),
            "quantity": int(payload["quantity"]),
        })

    elif disruption_type == "power_cut":
        if not payload.get("use_generator", False):
            day, shift = int(payload["day_index"]), int(payload["shift"])
            bucket_range = list(buckets_for_day_shift(day, shift, include_overtime=True))
            if bucket_range:
                span = (min(bucket_range), max(bucket_range) + 1)
                # A shop-wide power cut blocks every machine for the window.
                overlay.extra_blocked_ranges["__ALL__"] = [span]  # resolved against machines by caller
        # if use_generator=True, no scheduling constraint changes - handled purely as a cost line item.

    else:
        raise ValueError(f"Unknown disruption_type '{disruption_type}'")

    return overlay


def resolve_all_machines_blocking(overlay: Overlay, machine_ids: list[str]) -> None:
    if "__ALL__" in overlay.extra_blocked_ranges:
        spans = overlay.extra_blocked_ranges.pop("__ALL__")
        for mid in machine_ids:
            overlay.extra_blocked_ranges.setdefault(mid, []).extend(spans)


def apply_disruption(disruption_type: str, payload: dict, machines: list, operators: list, orders: list,
                      changeovers: dict, previous_result: dict, now_bucket: Optional[int] = None,
                      strategy: str = "cheapest", time_limit_seconds: float = 45.0) -> dict:
    overlay = build_overlay(disruption_type, payload)
    resolve_all_machines_blocking(overlay, [m["machine_id"] for m in machines])

    if now_bucket is not None:
        overlay.min_start_bucket = now_bucket
    elif "now_bucket" in payload:
        overlay.min_start_bucket = int(payload["now_bucket"])
    elif disruption_type == "machine_breakdown":
        # "Now" is naturally the moment the breakdown starts - everything
        # scheduled to have already started by then stays frozen.
        overlay.min_start_bucket = datetime_to_bucket(_parse_dt(payload["start_time"]))
    elif disruption_type == "power_cut":
        from calendar_utils import buckets_for_day_shift
        rng = list(buckets_for_day_shift(int(payload["day_index"]), int(payload["shift"])))
        overlay.min_start_bucket = min(rng) if rng else 0
    else:
        overlay.min_start_bucket = 0

    result = replan(machines, operators, orders, changeovers, previous_result,
                     overlay.min_start_bucket, overlay, strategy=strategy, time_limit_seconds=time_limit_seconds)

    if disruption_type == "power_cut" and payload.get("use_generator", False):
        result["comparison"]["generator_cost_note"] = (
            f"Generator option selected: affected shift billed at {GENERATOR_COST_MULTIPLIER}x "
            f"electricity-linked machine cost instead of losing the shift entirely."
        )

    result["owner_action"] = generate_owner_action(result, payload, disruption_type)
    return result


def generate_owner_action(replan_result: dict, payload: dict, disruption_type: str) -> dict:
    """a concrete recommended phone call, generated from the
    ACTUAL comparison metrics of this replan - not a canned sentence."""
    comparison = replan_result["comparison"]
    order_changes = [c for c in comparison["order_changes"] if c["moved"] or c["newly_late"]]
    if not order_changes:
        return {
            "has_action": False,
            "headline": "No customer-facing impact detected.",
            "detail": "The disruption was fully absorbed using spare capacity; no promised completion dates changed.",
        }

    # Prioritize Tier-1 customers, then whichever order slipped the most.
    def severity(c):
        tier_weight = {"Tier-1": 3, "Tier-2": 2, "Tier-3": 1}.get(c["customer_tier"], 1)
        return (c["newly_late"], tier_weight, c["delta_hours"])

    worst = max(order_changes, key=severity)
    overtime_delta = comparison["cost_delta"]["overtime_cost"]
    penalty_delta = comparison["cost_delta"]["penalty_cost"]

    headline = (f"Call {worst['customer']} ({worst['customer_tier']}) about order {worst['order_id']}: "
                f"promised delivery moved from {worst['old_completion']} to {worst['new_completion']}.")

    reason_parts = []
    if penalty_delta > 0:
        reason_parts.append(f"Without a new agreed date, the late-delivery penalty adds Rs.{penalty_delta:,.0f}.")
    if overtime_delta > 0:
        reason_parts.append(f"Holding the original date is currently costing Rs.{overtime_delta:,.0f} in overtime.")
    if not reason_parts:
        reason_parts.append("Confirming the new date with the customer avoids any last-minute surprise on the "
                             "shop floor.")

    return {
        "has_action": True,
        "headline": headline,
        "reasons": reason_parts,
        "order_id": worst["order_id"],
        "customer": worst["customer"],
        "customer_tier": worst["customer_tier"],
        "old_completion": worst["old_completion"],
        "new_completion": worst["new_completion"],
        "cost_delta": comparison["cost_delta"],
    }


def record_disruption(disruption_type: str, payload: dict, replan_result: Optional[dict] = None) -> int:
    return db.save_disruption(disruption_type, datetime.now().isoformat(), payload,
                               applied=replan_result is not None, replan_result=replan_result)
