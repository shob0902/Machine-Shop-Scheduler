import pytest

from scheduler.solver import solve_schedule, SchedulingError


@pytest.fixture(scope="module")
def small_schedule(small_master_data):
    machines, operators, orders, changeovers = small_master_data
    return solve_schedule(machines, operators, orders, changeovers, strategy="cheapest", time_limit_seconds=30)


def _machine_by_id(machines):
    return {m["machine_id"]: m for m in machines}


def _operator_by_id(operators):
    return {o["operator_id"]: o for o in operators}


def test_schedule_produces_operations(small_schedule):
    assert len(small_schedule["operations"]) > 0
    assert small_schedule["solver_status"] in ("OPTIMAL", "FEASIBLE", "FEASIBLE_HEURISTIC_FALLBACK")


def test_no_machine_overlaps(small_schedule):
    by_machine = {}
    for op in small_schedule["operations"]:
        by_machine.setdefault(op["machine_id"], []).append(op)
    for machine_id, ops in by_machine.items():
        ops = sorted(ops, key=lambda o: o["start_bucket"])
        for a, b in zip(ops, ops[1:]):
            assert a["end_bucket"] <= b["start_bucket"], f"Overlap on {machine_id}: {a} vs {b}"


def test_no_operator_overlaps(small_schedule):
    by_operator = {}
    for op in small_schedule["operations"]:
        by_operator.setdefault(op["operator_id"], []).append(op)
    for operator_id, ops in by_operator.items():
        ops = sorted(ops, key=lambda o: o["start_bucket"])
        for a, b in zip(ops, ops[1:]):
            assert a["end_bucket"] <= b["start_bucket"], f"Overlap for {operator_id}: {a} vs {b}"


def test_operation_precedence_respected(small_schedule):
    by_order = {}
    for op in small_schedule["operations"]:
        by_order.setdefault(op["order_id"], []).append(op)
    for order_id, ops in by_order.items():
        by_seq = {}
        for op in ops:
            by_seq.setdefault(op["sequence"], []).append(op)
        seqs = sorted(by_seq)
        for s1, s2 in zip(seqs, seqs[1:]):
            max_end_prev = max(o["end_bucket"] for o in by_seq[s1])
            min_start_next = min(o["start_bucket"] for o in by_seq[s2])
            assert min_start_next >= max_end_prev, f"Precedence violated in {order_id}: seq {s1} -> {s2}"


def test_valid_machine_assignment(small_schedule, small_master_data):
    machines, operators, orders, _ = small_master_data
    machines_by_id = _machine_by_id(machines)
    for op in small_schedule["operations"]:
        machine = machines_by_id[op["machine_id"]]
        assert op["operation_type"] in machine["capabilities"], \
            f"{op['machine_id']} cannot perform {op['operation_type']}"


def test_valid_operator_assignment(small_schedule, small_master_data):
    machines, operators, orders, _ = small_master_data
    operators_by_id = _operator_by_id(operators)
    for op in small_schedule["operations"]:
        operator = operators_by_id[op["operator_id"]]
        assert op["operation_type"] in operator["skills"], \
            f"{op['operator_id']} not skilled in {op['operation_type']}"
        assert op["machine_id"] in operator["qualified_machines"], \
            f"{op['operator_id']} not qualified for {op['machine_id']}"


def test_no_work_during_maintenance(small_schedule, small_master_data):
    machines, *_ = small_master_data
    from config import BUCKETS_PER_DAY_WITH_OT
    for m in machines:
        for w in m["maintenance_windows"]:
            base = w["day_index"] * BUCKETS_PER_DAY_WITH_OT
            ws = base + int(round(w["start_hour"] * 4))
            we = base + int(round(w["end_hour"] * 4))
            for op in small_schedule["operations"]:
                if op["machine_id"] != m["machine_id"]:
                    continue
                overlap = op["start_bucket"] < we and ws < op["end_bucket"]
                assert not overlap, f"Operation {op['operation_id']} scheduled during maintenance on {m['machine_id']}"


def test_no_work_before_material_availability(small_schedule, small_master_data):
    from calendar_utils import datetime_to_bucket
    from datetime import datetime
    machines, operators, orders, _ = small_master_data
    ops_by_order = {}
    for op in small_schedule["operations"]:
        ops_by_order.setdefault(op["order_id"], []).append(op)
    for o in orders:
        ops = ops_by_order.get(o["order_id"], [])
        if not ops:
            continue
        material_bucket = datetime_to_bucket(datetime.fromisoformat(o["material_available_date"]))
        first_start = min(op["start_bucket"] for op in ops)
        assert first_start >= material_bucket, f"{o['order_id']} started before material was available"


def test_solver_reports_infeasible_cleanly(small_master_data):
    """An operator with zero qualified machines for a required operation type
    should be reported through SchedulingError, not crash the process."""
    machines, operators, orders, changeovers = small_master_data
    broken_orders = [dict(orders[0])]
    broken_orders[0] = dict(broken_orders[0])
    broken_orders[0]["routing"] = [dict(op) for op in broken_orders[0]["routing"]]
    # Force an operation type nothing in the shop can perform.
    broken_orders[0]["routing"][0]["operation_type"] = "Welding"
    with pytest.raises(SchedulingError) as exc_info:
        solve_schedule(machines, operators, broken_orders, changeovers, strategy="cheapest", time_limit_seconds=5)
    assert exc_info.value.suggestion
