from scheduler.solver import solve_schedule
from scheduler.objectives import STRATEGIES


def test_all_three_strategies_exist():
    assert set(STRATEGIES) == {"cheapest", "most_on_time", "most_robust"}


def test_all_strategies_produce_valid_schedules(small_master_data):
    machines, operators, orders, changeovers = small_master_data
    for strategy in STRATEGIES:
        result = solve_schedule(machines, operators, orders, changeovers, strategy=strategy, time_limit_seconds=30)
        assert result["strategy"] == strategy
        assert len(result["operations"]) > 0
        assert result["cost_breakdown"]["total_cost"] >= 0
        assert 0 <= result["metrics"]["on_time_percentage"] <= 100
