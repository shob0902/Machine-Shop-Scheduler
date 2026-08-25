import pytest

from scheduler.models import Overlay
from scheduler.replanner import replan
from scheduler.solver import solve_schedule
from calendar_utils import bucket_to_datetime


@pytest.fixture(scope="module")
def baseline(small_master_data):
    machines, operators, orders, changeovers = small_master_data
    return solve_schedule(machines, operators, orders, changeovers, strategy="cheapest", time_limit_seconds=30)


def test_machine_breakdown_replan_preserves_started_work(small_master_data, baseline):
    machines, operators, orders, changeovers = small_master_data
    # Pick a machine actually used partway through the schedule as the "now" pivot.
    ops = sorted(baseline["operations"], key=lambda o: o["start_bucket"])
    now_bucket = ops[len(ops) // 2]["start_bucket"]
    target_machine = ops[-1]["machine_id"]

    overlay = Overlay()
    overlay.extra_blocked_ranges[target_machine] = [(now_bucket, now_bucket + 16)]
    overlay.machine_status_override[target_machine] = "down"
    overlay.min_start_bucket = now_bucket

    result = replan(machines, operators, orders, changeovers, baseline, now_bucket, overlay,
                     strategy="cheapest", time_limit_seconds=30)

    assert result["frozen_operation_count"] >= 1
    for op in result["operations"]:
        if op["status"] == "frozen":
            # Frozen means "already started by now" (completed OR in
            # progress) - this preserves in-progress work too, so its
            # end_bucket may fall after now_bucket.
            assert op["start_bucket"] <= now_bucket
    # Nothing should be scheduled on the broken machine inside the blocked window.
    for op in result["operations"]:
        if op["machine_id"] == target_machine:
            overlap = op["start_bucket"] < now_bucket + 16 and now_bucket < op["end_bucket"]
            assert not overlap
    assert "comparison" in result
    assert "disruption_cost" in result["comparison"]


def test_operator_absence_replan(small_master_data, baseline):
    machines, operators, orders, changeovers = small_master_data
    absent_operator = baseline["operations"][0]["operator_id"]
    day = baseline["operations"][0]["day_index"]
    shift = baseline["operations"][0]["shift"]

    overlay = Overlay()
    overlay.operator_extra_absences[absent_operator] = [(day, shift)]
    result = replan(machines, operators, orders, changeovers, baseline, 0, overlay,
                     strategy="cheapest", time_limit_seconds=30)
    for op in result["operations"]:
        if op["operator_id"] == absent_operator:
            assert not (op["day_index"] == day and op["shift"] == shift)


def test_material_delay_replan(small_master_data, baseline):
    machines, operators, orders, changeovers = small_master_data
    order_id = orders[0]["order_id"]
    from calendar_utils import datetime_to_bucket
    from datetime import datetime, timedelta
    new_date = datetime.fromisoformat(orders[0]["material_available_date"]) + timedelta(days=3)

    overlay = Overlay()
    overlay.material_overrides[order_id] = datetime_to_bucket(new_date)
    result = replan(machines, operators, orders, changeovers, baseline, 0, overlay,
                     strategy="cheapest", time_limit_seconds=30)

    order_ops = [op for op in result["operations"] if op["order_id"] == order_id]
    first_start = min(op["start_bucket"] for op in order_ops)
    assert first_start >= datetime_to_bucket(new_date)


def test_rework_replan_adds_new_operation(small_master_data, baseline):
    machines, operators, orders, changeovers = small_master_data
    order_id = orders[0]["order_id"]

    overlay = Overlay()
    overlay.rework_events.append({"order_id": order_id, "operation_id": None, "quantity": 25})
    result = replan(machines, operators, orders, changeovers, baseline, 0, overlay,
                     strategy="cheapest", time_limit_seconds=30)

    rework_ops = [op for op in result["operations"] if op.get("is_rework")]
    assert len(rework_ops) >= 1
    assert result["comparison"]["moved_operation_count"] >= 0
