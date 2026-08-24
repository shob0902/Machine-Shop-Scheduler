from config import PART_FAMILIES, OPERATION_TO_MACHINE_TYPES


def test_machine_count(full_master_data):
    machines, *_ = full_master_data
    assert len(machines) == 14


def test_order_count_approximately_25(full_master_data):
    _, _, orders, _ = full_master_data
    assert 20 <= len(orders) <= 30


def test_operations_per_order_in_range(full_master_data):
    _, _, orders, _ = full_master_data
    for o in orders:
        steps = len(set(op["sequence"] for op in o["routing"]))
        assert 3 <= steps <= 6, f"{o['order_id']} has {steps} routing steps"


def test_machine_capabilities_are_realistic(full_master_data):
    machines, *_ = full_master_data
    all_caps = {c for m in machines for c in m["capabilities"]}
    assert all_caps <= set(OPERATION_TO_MACHINE_TYPES.keys())
    for m in machines:
        assert len(m["capabilities"]) >= 1


def test_only_three_operators_qualified_for_grinding(full_master_data):
    _, operators, _, _ = full_master_data
    grinders = [o for o in operators if "Grinding" in o["skills"]]
    assert len(grinders) == 3


def test_changeover_matrix_covers_all_families(full_master_data):
    *_, changeovers = full_master_data
    for f1 in PART_FAMILIES:
        for f2 in PART_FAMILIES:
            assert f1 in changeovers and f2 in changeovers[f1]
            assert changeovers[f1][f2] > 0


def test_changeover_same_family_cheaper_than_cross_family_on_average(full_master_data):
    *_, changeovers = full_master_data
    same = [changeovers[f][f] for f in PART_FAMILIES]
    cross = [changeovers[f1][f2] for f1 in PART_FAMILIES for f2 in PART_FAMILIES if f1 != f2]
    assert sum(same) / len(same) < sum(cross) / len(cross)


def test_valid_routing_operation_types(full_master_data):
    _, _, orders, _ = full_master_data
    for o in orders:
        for op in o["routing"]:
            assert op["operation_type"] in OPERATION_TO_MACHINE_TYPES
            assert op["quantity"] > 0
            assert op["minutes_per_piece"] > 0


def test_some_orders_have_delayed_material(full_master_data):
    _, _, orders, _ = full_master_data
    delayed = [o for o in orders if o["material_available_date"] > o["release_date"]]
    assert len(delayed) >= 1


def test_breakdown_history_has_required_fields(full_master_data):
    machines, *_ = full_master_data
    for m in machines:
        for b in m["breakdown_history"]:
            assert {"breakdown_id", "machine_id", "start_time", "end_time",
                     "duration_minutes", "failure_type", "severity"} <= set(b.keys())


def test_maintenance_windows_exist(full_master_data):
    machines, *_ = full_master_data
    total_windows = sum(len(m["maintenance_windows"]) for m in machines)
    assert total_windows >= 1


def test_tier1_customer_dominates_order_book(full_master_data):
    _, _, orders, _ = full_master_data
    tier1 = [o for o in orders if o["customer_tier"] == "Tier-1"]
    assert len(tier1) >= 1
    tier1_customers = {o["customer"] for o in tier1}
    assert len(tier1_customers) == 1  # one dominant Tier-1 customer, per the scenario
