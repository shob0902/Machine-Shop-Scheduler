import pytest

from scheduler.solver import solve_schedule


@pytest.fixture(scope="module")
def schedule(small_master_data):
    machines, operators, orders, changeovers = small_master_data
    return solve_schedule(machines, operators, orders, changeovers, strategy="cheapest", time_limit_seconds=30)


def test_cost_breakdown_components_present(schedule):
    c = schedule["cost_breakdown"]
    for key in ("operating_cost", "overtime_cost", "penalty_cost", "changeover_cost",
                "other_disruption_cost", "total_cost"):
        assert key in c
        assert c[key] >= 0


def test_cost_components_sum_to_total(schedule):
    c = schedule["cost_breakdown"]
    computed = c["operating_cost"] + c["overtime_cost"] + c["penalty_cost"] + c["changeover_cost"]
    assert abs(computed - c["total_cost"]) < 1.0


def test_overtime_cost_only_when_overtime_hours_exist(schedule):
    c = schedule["cost_breakdown"]
    m = schedule["metrics"]
    if m["overtime_hours"] == 0:
        assert c["overtime_cost"] == 0
    else:
        assert c["overtime_cost"] > 0


def test_penalty_cost_only_when_late_orders_exist(schedule):
    c = schedule["cost_breakdown"]
    m = schedule["metrics"]
    if m["late_orders"] == 0:
        assert c["penalty_cost"] == 0
