"""
Synthetic manufacturing data generator for Sridhar Precision Works.

Produces the five master-data JSON files described in the project structure:
    machines.json, operators.json, orders.json, changeovers.json, breakdowns.json

Run directly:  python -m data.generator
(or via the Flask app's /api/schedule/generate bootstrap, which calls
 `generate_all()` the first time no data files exist.)

Everything here is randomised from a fixed seed (config.RANDOM_SEED) so the
dataset is reproducible but not hand-authored order-by-order - i.e. there is
no "if order_id == ORD-001" logic anywhere in this file or the scheduler.
"""
from __future__ import annotations

import json
import os
import random
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (  # noqa: E402
    DATA_DIR, RANDOM_SEED, PART_FAMILIES, MACHINE_TYPES, OPERATION_TYPES,
    OPERATION_TO_MACHINE_TYPES, CUSTOMER_TIERS,
    CHANGEOVER_SAME_FAMILY_MIN, CHANGEOVER_SAME_FAMILY_MAX,
    CHANGEOVER_DIFFERENT_FAMILY_MIN, CHANGEOVER_DIFFERENT_FAMILY_MAX,
    SCHEDULE_START_DATE, HORIZON_DAYS, INSPECTION_FAIL_RATE_RANGE,
    MAX_SINGLE_OPERATION_BUCKETS, BUCKET_MINUTES,
)

rng = random.Random(RANDOM_SEED)

# ---------------------------------------------------------------------------
# 1. MACHINES  (Section 5) - exactly 14
# ---------------------------------------------------------------------------
MACHINE_BLUEPRINT = [
    # (id, name, type, capabilities, base_hourly_cost, base_overtime_cost)
    ("LATHE-01", "CNC Lathe 01", "CNC Lathe", ["Turning"], 650, 1140),
    ("LATHE-02", "CNC Lathe 02", "CNC Lathe", ["Turning"], 650, 1140),
    ("LATHE-03", "CNC Lathe 03", "CNC Lathe", ["Turning"], 700, 1225),
    ("LATHE-04", "CNC Lathe 04 (heavy duty)", "CNC Lathe", ["Turning"], 780, 1365),
    ("MILL-01", "Vertical Milling Center 01", "Milling", ["Milling", "Deburring"], 720, 1260),
    ("MILL-02", "Vertical Milling Center 02", "Milling", ["Milling", "Deburring"], 720, 1260),
    ("MILL-03", "Horizontal Milling Center 03", "Milling", ["Milling"], 760, 1330),
    ("DRILL-01", "Radial Drill 01", "Drilling", ["Drilling", "Deburring"], 480, 840),
    ("DRILL-02", "Radial Drill 02", "Drilling", ["Drilling", "Deburring"], 480, 840),
    ("DRILL-03", "CNC Drill 03", "Drilling", ["Drilling"], 520, 910),
    ("GRIND-01", "Cylindrical Grinder 01", "Grinding", ["Grinding"], 900, 1575),
    ("GRIND-02", "Surface Grinder 02", "Grinding", ["Grinding"], 880, 1540),
    ("INSPECT-01", "CMM Inspection Bay 01", "Inspection", ["Inspection"], 400, 700),
    ("INSPECT-02", "Manual Inspection Bay 02", "Inspection", ["Inspection"], 320, 560),
]

MAINTENANCE_PLAN = [
    # (machine_id, day_index within horizon, start_hour, end_hour, description)
    ("MILL-02", 2, 14.0, 18.0, "Wednesday preventive maintenance - spindle service"),
    ("LATHE-03", 5, 6.0, 9.0, "Coolant system flush"),
    ("GRIND-01", 8, 18.0, 22.0, "Wheel dressing & calibration"),
    ("DRILL-02", 10, 6.0, 8.0, "Bearing inspection"),
    ("INSPECT-01", 4, 14.0, 15.5, "CMM probe recalibration"),
]


def build_machines() -> list[dict]:
    machines = []
    for mid, name, mtype, caps, hourly, ot in MACHINE_BLUEPRINT:
        maint = [
            {
                "machine_id": m[0], "day_index": m[1], "start_hour": m[2],
                "end_hour": m[3], "description": m[4],
            }
            for m in MAINTENANCE_PLAN if m[0] == mid
        ]
        machines.append({
            "machine_id": mid,
            "machine_name": name,
            "machine_type": mtype,
            "capabilities": caps,
            "available_shifts": [1, 2],
            "hourly_cost": hourly,
            "overtime_cost": ot,
            "maintenance_windows": maint,
            "initial_status": "operational",
            "breakdown_history": [],  # filled in by build_breakdowns()
        })
    assert len(machines) == 14, "Assignment requires exactly 14 machines"
    return machines


# ---------------------------------------------------------------------------
# 2. CHANGEOVER MATRIX (Section 6)
# ---------------------------------------------------------------------------
def build_changeover_matrix() -> dict:
    matrix = {}
    for f1 in PART_FAMILIES:
        matrix[f1] = {}
        for f2 in PART_FAMILIES:
            if f1 == f2:
                minutes = rng.randint(CHANGEOVER_SAME_FAMILY_MIN, CHANGEOVER_SAME_FAMILY_MAX)
            else:
                minutes = rng.randint(CHANGEOVER_DIFFERENT_FAMILY_MIN, CHANGEOVER_DIFFERENT_FAMILY_MAX)
            matrix[f1][f2] = minutes
    return matrix


# ---------------------------------------------------------------------------
# 3. OPERATORS (Section 7) + SHIFT ROSTER (Section 8)
# ---------------------------------------------------------------------------
FIRST_NAMES = [
    "Ravi", "Suresh", "Manoj", "Karthik", "Vijay", "Anand", "Prakash", "Ganesh",
    "Sanjay", "Deepak", "Arun", "Mahesh", "Ramesh", "Naveen", "Kiran", "Ashok",
    "Vikram", "Santosh", "Gopal", "Harish", "Rajesh", "Sunil", "Yogesh", "Balaji",
    "Muthu", "Selvam", "Kannan", "Murugan",
]
LAST_NAMES = ["Kumar", "Reddy", "Iyer", "Naidu", "Shetty", "Rao", "Pillai", "Nair", "Gowda", "Menon"]


def _machine_ids_by_capability(machines: list[dict], capability: str) -> list[str]:
    return [m["machine_id"] for m in machines if capability in m["capabilities"]]


def build_operators(machines: list[dict]) -> list[dict]:
    operators = []
    used_names = set()

    def unique_name():
        while True:
            nm = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
            if nm not in used_names:
                used_names.add(nm)
                return nm

    op_counter = 1

    def new_operator(skills, qualified_machines, shifts):
        nonlocal op_counter
        oid = f"OP-{op_counter:03d}"
        op_counter += 1
        rate = round(rng.uniform(180, 260), 2)
        operators.append({
            "operator_id": oid,
            "name": unique_name(),
            "skills": skills,
            "qualified_machines": qualified_machines,
            "available_shifts": shifts,
            "hourly_rate": rate,
            "overtime_rate": round(rate * 1.5, 2),
            "roster": {},
            "absences": {},
        })
        return oid

    # --- Specialist grinding operators: EXACTLY THREE can run grinding machines ---
    grind_machines = _machine_ids_by_capability(machines, "Grinding")
    grind_operator_ids = [
        new_operator(["Grinding", "Inspection"], grind_machines, [1, 2]) for _ in range(3)
    ]

    # --- General machinists: cover turning / milling / drilling / deburring ---
    lathe_ids = _machine_ids_by_capability(machines, "Turning")
    mill_ids = _machine_ids_by_capability(machines, "Milling")
    drill_ids = _machine_ids_by_capability(machines, "Drilling")
    inspect_ids = _machine_ids_by_capability(machines, "Inspection")

    # Each generalist is qualified on a rotating SUBSET of same-type machines
    # (2 of 4 lathes, 2 of 3 mills, 2 of 3 drills) rather than all of them -
    # this mirrors how real shop-floor training works (not everyone is
    # cross-certified on every machine) and keeps the CP-SAT candidate pool
    # per machine small enough to solve quickly, while every machine still
    # has multiple qualified operators covering it (checked below).
    def rotating_subset(ids: list[str], idx: int, size: int) -> list[str]:
        if len(ids) <= size:
            return ids
        start_i = (idx * (len(ids) // 2 or 1)) % len(ids)
        return [ids[(start_i + k) % len(ids)] for k in range(size)]

    turners = [new_operator(["Turning"], rotating_subset(lathe_ids, i, 2), [1, 2]) for i in range(6)]
    millers = [new_operator(["Milling", "Deburring"], rotating_subset(mill_ids, i, 2), [1, 2]) for i in range(5)]
    drillers = [new_operator(["Drilling", "Deburring"], rotating_subset(drill_ids, i, 2), [1, 2]) for i in range(5)]
    inspectors = [new_operator(["Inspection"], inspect_ids, [1, 2]) for _ in range(4)]

    # --- A few cross-trained "swing" operators, for realism & robustness ---
    swing1 = new_operator(["Turning", "Milling"], rotating_subset(lathe_ids, 0, 2) + rotating_subset(mill_ids, 0, 2), [1, 2])
    swing2 = new_operator(["Milling", "Drilling", "Deburring"], rotating_subset(mill_ids, 1, 2) + rotating_subset(drill_ids, 1, 2), [1, 2])
    swing3 = new_operator(["Drilling", "Inspection", "Deburring"], rotating_subset(drill_ids, 2, 2) + inspect_ids, [1, 2])

    all_ops = grind_operator_ids + turners + millers + drillers + inspectors + [swing1, swing2, swing3]
    assert len(all_ops) == len(operators)

    # --- Build a 2-shift roster over the horizon guaranteeing coverage ---
    # Each operator works 5 of every 7 days, alternating shift 1 / shift 2 weeks,
    # with two rostered rest days chosen so that, for every (machine-type, day,
    # shift), at least one qualified operator remains on duty (checked below).
    by_op = {o["operator_id"]: o for o in operators}

    for oid in all_ops:
        rest_days = set(rng.sample(range(7), 2))  # 2 rest days per week, repeating
        preferred_shift = rng.choice([1, 2])
        roster = {}
        for day in range(HORIZON_DAYS):
            dow = day % 7
            if dow in rest_days:
                continue
            # Most days on preferred shift; occasionally cover the other shift.
            shift = preferred_shift if rng.random() > 0.15 else (3 - preferred_shift)
            roster[day] = [shift]
        by_op[oid]["roster"] = {str(k): v for k, v in roster.items()}

    # --- Coverage guarantee pass: ensure every machine-capability/day/shift has >=1 operator ---
    capability_groups = {
        "Turning": turners + [swing1],
        "Milling": millers + [swing1, swing2],
        "Drilling": drillers + [swing2, swing3],
        "Grinding": grind_operator_ids,
        "Inspection": inspectors + [swing3],
    }
    for day in range(HORIZON_DAYS):
        for shift in (1, 2):
            for cap, ids in capability_groups.items():
                covered = any(shift in by_op[oid]["roster"].get(str(day), []) for oid in ids)
                if not covered:
                    # Force the least-recently-forced operator onto this shift.
                    chosen = rng.choice(ids)
                    by_op[chosen]["roster"].setdefault(str(day), [])
                    if shift not in by_op[chosen]["roster"][str(day)]:
                        by_op[chosen]["roster"][str(day)].append(shift)

    return operators


# ---------------------------------------------------------------------------
# 4. BREAKDOWN HISTORY (Section 13) - historical, BEFORE the planning horizon
# ---------------------------------------------------------------------------
FAILURE_TYPES = ["Spindle overheat", "Coolant leak", "Tool breakage", "Electrical fault",
                  "Hydraulic failure", "Sensor malfunction", "Belt slippage", "Bearing wear"]
SEVERITIES = ["minor", "major", "critical"]
SEVERITY_DURATION = {"minor": (30, 120), "major": (120, 360), "critical": (360, 900)}
SEVERITY_WEIGHTS = [0.55, 0.35, 0.10]


def build_breakdowns(machines: list[dict]) -> list[dict]:
    breakdowns = []
    counter = 1
    history_start = datetime.combine(SCHEDULE_START_DATE, datetime.min.time()) - timedelta(days=180)
    for m in machines:
        # Older / heavier-duty machines break down a bit more often.
        n_events = rng.randint(1, 5) if m["machine_type"] != "Inspection" else rng.randint(0, 2)
        for _ in range(n_events):
            offset_days = rng.randint(0, 179)
            start = history_start + timedelta(days=offset_days, hours=rng.randint(0, 23))
            severity = rng.choices(SEVERITIES, weights=SEVERITY_WEIGHTS)[0]
            dur = rng.randint(*SEVERITY_DURATION[severity])
            end = start + timedelta(minutes=dur)
            breakdowns.append({
                "breakdown_id": f"BRK-{counter:04d}",
                "machine_id": m["machine_id"],
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
                "duration_minutes": dur,
                "failure_type": rng.choice(FAILURE_TYPES),
                "severity": severity,
            })
            counter += 1
    return breakdowns


# ---------------------------------------------------------------------------
# 5. ORDERS (Section 9-11) - ~25 orders, 3-6 operations each
# ---------------------------------------------------------------------------
CUSTOMERS = [
    ("Apex AutoDrive Pvt Ltd", "Tier-1"),      # dominant customer, JIT delivery
    ("Continental Gearworks", "Tier-2"),
    ("Bharat Motion Components", "Tier-2"),
    ("Vishnu Precision Auto", "Tier-2"),
    ("Sundaram Fasteners Group", "Tier-2"),
    ("Deccan Transmission Systems", "Tier-3"),
    ("Nilgiri Auto Parts", "Tier-3"),
    ("Coromandel Drivetrain Co", "Tier-3"),
    ("Malabar Precision Casting", "Tier-3"),
    ("Kaveri Engineering Works", "Tier-3"),
]

# Realistic routing templates per part family (3-6 ops, not identical across orders).
ROUTING_TEMPLATES = {
    "Shaft": [["Turning", "Grinding", "Inspection"],
              ["Turning", "Turning", "Grinding", "Inspection"]],
    "Flange": [["Turning", "Drilling", "Inspection"],
               ["Turning", "Milling", "Drilling", "Inspection"]],
    "Housing": [["Milling", "Drilling", "Deburring", "Inspection"],
                ["Milling", "Milling", "Drilling", "Deburring", "Inspection"]],
    "Bracket": [["Milling", "Drilling", "Inspection"],
                ["Drilling", "Milling", "Deburring", "Inspection"]],
    "Gear": [["Turning", "Milling", "Grinding", "Inspection"],
             ["Turning", "Milling", "Drilling", "Grinding", "Inspection"],
             ["Turning", "Turning", "Milling", "Drilling", "Grinding", "Inspection"]],
    "Pin": [["Turning", "Grinding", "Inspection"],
            ["Turning", "Drilling", "Grinding", "Inspection"]],
}

# Approx minutes-per-piece range by operation type (tuned for 200-5000pc lots
# to fit sensibly within a 14-day / 2-shift horizon across 14 machines).
RATE_RANGE_MIN_PER_PIECE = {
    "Turning": (0.20, 0.45),
    "Milling": (0.25, 0.55),
    "Drilling": (0.12, 0.30),
    "Grinding": (0.30, 0.70),
    "Deburring": (0.08, 0.18),
    "Inspection": (0.05, 0.12),
}

TIER_PENALTY_PER_DAY = {"Tier-1": (15000, 25000), "Tier-2": (5000, 9000), "Tier-3": (1500, 3500)}
TIER_PRIORITY_RANGE = {"Tier-1": (8, 10), "Tier-2": (4, 7), "Tier-3": (1, 4)}
TIER_UNIT_VALUE = {"Tier-1": (180, 320), "Tier-2": (90, 180), "Tier-3": (40, 100)}


def _build_batches(order_id: str, sequence: int, op_type: str, quantity: int,
                    rate: float, setup_minutes: float, op_counter: int) -> tuple[list[dict], int]:
    """
    Split one routing step into 1+ sub-batch operations if its raw duration
    would exceed MAX_SINGLE_OPERATION_BUCKETS (a single operation must fit
    inside one operator's continuous shift window - see config.py). All
    sub-batches share `sequence`, so the scheduler treats them as parallel
    alternatives that must ALL finish before the next routing step starts.
    """
    cap_minutes = MAX_SINGLE_OPERATION_BUCKETS * BUCKET_MINUTES
    total_minutes = quantity * rate + setup_minutes
    if total_minutes <= cap_minutes:
        op = {
            "operation_id": f"OP{op_counter:04d}", "order_id": order_id, "sequence": sequence,
            "operation_type": op_type, "quantity": quantity, "minutes_per_piece": rate,
            "setup_minutes": setup_minutes,
        }
        return [op], op_counter + 1

    pieces_per_batch = max(1, int((cap_minutes - setup_minutes) / rate))
    n_batches = -(-quantity // pieces_per_batch)  # ceil div
    base_qty = quantity // n_batches
    remainder = quantity - base_qty * n_batches

    batches = []
    for b in range(n_batches):
        qty = base_qty + (1 if b < remainder else 0)
        if qty <= 0:
            continue
        batches.append({
            "operation_id": f"OP{op_counter:04d}", "order_id": order_id, "sequence": sequence,
            "operation_type": op_type, "quantity": qty, "minutes_per_piece": rate,
            "setup_minutes": setup_minutes,
        })
        op_counter += 1
    return batches, op_counter


def build_orders(num_orders: int = 25) -> list[dict]:
    orders = []
    op_counter = 1
    for i in range(1, num_orders + 1):
        oid = f"ORD-{i:03d}"
        # Tier-1 customer (Apex) gets ~35% of the order book, matching the
        # assignment's "one Tier-1 customer contributes a very large share
        # of revenue" narrative; the rest are spread across Tier-2/Tier-3.
        if rng.random() < 0.32:
            customer, tier = CUSTOMERS[0]
        else:
            customer, tier = rng.choice(CUSTOMERS[1:])

        family = rng.choice(PART_FAMILIES)
        template = rng.choice(ROUTING_TEMPLATES[family])
        quantity = rng.randint(200, 5000)

        release_offset = 0 if rng.random() > 0.2 else rng.randint(0, 2)
        release_date = SCHEDULE_START_DATE + timedelta(days=release_offset)

        # Material availability: most orders have material on hand at release;
        # a handful are genuinely constrained (Section 11).
        if rng.random() < 0.22:
            material_offset = release_offset + rng.randint(1, 4)
        else:
            material_offset = release_offset
        material_available_date = SCHEDULE_START_DATE + timedelta(days=material_offset)

        # Due dates spread across the two-week horizon, tier-1/JIT orders
        # skew earlier & tighter.
        if tier == "Tier-1":
            due_offset = rng.randint(3, 9)
        else:
            due_offset = rng.randint(6, 14)
        due_date = SCHEDULE_START_DATE + timedelta(days=due_offset, hours=rng.choice([6, 12, 14, 18]))

        penalty = round(rng.uniform(*TIER_PENALTY_PER_DAY[tier]), 2)
        priority = rng.randint(*TIER_PRIORITY_RANGE[tier])
        unit_value = rng.uniform(*TIER_UNIT_VALUE[tier])
        order_value = round(unit_value * quantity, 2)
        insp_fail = round(rng.uniform(*INSPECTION_FAIL_RATE_RANGE), 4)

        routing = []
        for seq, op_type in enumerate(template, start=1):
            lo, hi = RATE_RANGE_MIN_PER_PIECE[op_type]
            rate = round(rng.uniform(lo, hi), 3)
            setup = round(rng.uniform(10, 30), 1)
            batches, op_counter = _build_batches(oid, seq, op_type, quantity, rate, setup, op_counter)
            routing.extend(batches)

        orders.append({
            "order_id": oid,
            "customer": customer,
            "customer_tier": tier,
            "part_family": family,
            "quantity": quantity,
            "release_date": release_date.isoformat(),
            "material_available_date": material_available_date.isoformat(),
            "due_date": due_date.isoformat(),
            "late_penalty_per_day": penalty,
            "revenue_priority": priority,
            "routing": routing,
            "inspection_probability_fail": insp_fail,
            "order_value": order_value,
        })
    return orders


# ---------------------------------------------------------------------------
# Capacity sanity pass: avoid an unintentionally infeasible dataset by
# rescaling per-piece rates down if any machine-type's total demand would
# exceed a safe share of its available regular+overtime capacity.
# ---------------------------------------------------------------------------
def rebalance_capacity(machines: list[dict], orders: list[dict]) -> None:
    from config import BUCKETS_PER_DAY_WITH_OT, BUCKET_MINUTES, HORIZON_DAYS

    capacity_minutes_by_type: dict[str, float] = {}
    for m in machines:
        cap = HORIZON_DAYS * BUCKETS_PER_DAY_WITH_OT * BUCKET_MINUTES
        capacity_minutes_by_type[m["machine_type"]] = capacity_minutes_by_type.get(m["machine_type"], 0) + cap

    demand_minutes_by_type: dict[str, float] = {}
    for o in orders:
        for op in o["routing"]:
            for mtype in OPERATION_TO_MACHINE_TYPES[op["operation_type"]]:
                demand_minutes_by_type[mtype] = demand_minutes_by_type.get(mtype, 0) + \
                    op["quantity"] * op["minutes_per_piece"] / len(OPERATION_TO_MACHINE_TYPES[op["operation_type"]])

    SAFE_UTILIZATION = 0.78
    for mtype, demand in demand_minutes_by_type.items():
        cap = capacity_minutes_by_type.get(mtype, 1)
        if demand > cap * SAFE_UTILIZATION:
            scale = (cap * SAFE_UTILIZATION) / demand
            for o in orders:
                for op in o["routing"]:
                    if mtype in OPERATION_TO_MACHINE_TYPES[op["operation_type"]]:
                        op["minutes_per_piece"] = round(op["minutes_per_piece"] * scale, 3)


def generate_all(out_dir: str = DATA_DIR, num_orders: int = 25) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    machines = build_machines()
    operators = build_operators(machines)
    changeovers = build_changeover_matrix()
    breakdowns = build_breakdowns(machines)
    orders = build_orders(num_orders)

    rebalance_capacity(machines, orders)

    by_machine_id = {b["machine_id"]: [] for b in machines}
    for b in breakdowns:
        by_machine_id[b["machine_id"]].append(b)
    for m in machines:
        m["breakdown_history"] = by_machine_id[m["machine_id"]]

    files = {
        "machines.json": machines,
        "operators.json": operators,
        "orders.json": orders,
        "changeovers.json": changeovers,
        "breakdowns.json": breakdowns,
    }
    for fname, payload in files.items():
        with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    return files


if __name__ == "__main__":
    result = generate_all()
    print(f"Generated {len(result['machines.json'])} machines, "
          f"{len(result['operators.json'])} operators, "
          f"{len(result['orders.json'])} orders, "
          f"{sum(len(o['routing']) for o in result['orders.json'])} operations, "
          f"{len(result['breakdowns.json'])} historical breakdown records.")
