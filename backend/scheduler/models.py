"""
Internal solver-facing data structures.

`build_solver_input()` turns the raw master-data JSON (machines, operators,
orders, changeovers) plus an optional `Overlay` (used by the replanner to
represent a disruption) into a flat list of `Task` objects ready to be wired
into the CP-SAT model by scheduler/constraints.py.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from config import (
    BUCKET_MINUTES, OPERATION_TO_MACHINE_TYPES, BUCKETS_PER_DAY_WITH_OT, PART_FAMILIES,
)
from calendar_utils import (
    datetime_to_bucket, buckets_for_day_shift, TOTAL_BUCKETS,
)


@dataclass
class Task:
    """One schedulable unit of work (an operation, or rework sub-batch)."""
    operation_id: str
    order_id: str
    sequence: float
    operation_type: str
    quantity: int
    part_family: str
    duration_buckets: int
    eligible_machines: List[str]
    # (machine_id, operator_id) pairs valid for this task
    assignment_options: List[Tuple[str, str]]
    earliest_start_bucket: int = 0
    due_bucket: Optional[int] = None
    is_rework: bool = False
    frozen: bool = False
    frozen_machine: Optional[str] = None
    frozen_operator: Optional[str] = None
    frozen_start: Optional[int] = None
    frozen_end: Optional[int] = None


@dataclass
class OrderInfo:
    order_id: str
    customer: str
    customer_tier: str
    part_family: str
    due_bucket: int
    late_penalty_per_day: float
    revenue_priority: int
    order_value: float
    task_ids: List[str] = field(default_factory=list)


@dataclass
class MachineInfo:
    machine_id: str
    machine_name: str
    machine_type: str
    hourly_cost: float
    overtime_cost: float
    blocked_ranges: List[Tuple[int, int]] = field(default_factory=list)  # maintenance + breakdowns
    status: str = "operational"


@dataclass
class OperatorInfo:
    operator_id: str
    name: str
    hourly_rate: float
    overtime_rate: float
    blocked_ranges: List[Tuple[int, int]] = field(default_factory=list)


@dataclass
class Overlay:
    """A disruption overlay applied on top of the base dataset before solving."""
    frozen_task_ids: set = field(default_factory=set)
    task_assignments: Dict[str, dict] = field(default_factory=dict)  # operation_id -> {machine_id, operator_id, start, end}
    extra_blocked_ranges: Dict[str, List[Tuple[int, int]]] = field(default_factory=dict)
    machine_status_override: Dict[str, str] = field(default_factory=dict)
    operator_extra_absences: Dict[str, List[Tuple[int, int]]] = field(default_factory=dict)  # operator -> (day, shift)
    material_overrides: Dict[str, int] = field(default_factory=dict)  # order_id -> new earliest bucket for its first task
    rework_events: List[dict] = field(default_factory=list)  # raw ReworkEvent-like dicts
    min_start_bucket: int = 0  # "now" - nothing can be (re)planned before this bucket


def minutes_to_buckets(minutes: float) -> int:
    return max(1, math.ceil(minutes / BUCKET_MINUTES))


def _machine_capable(machine: dict, op_type: str) -> bool:
    return op_type in machine["capabilities"]


def restrict_machines_by_family(machine_ids: List[str], family: str) -> List[str]:
    """
    Pre-qualify each part family on a realistic SUBSET of same-type machines
    (tooling/fixture proximity) rather than treating every machine of a type
    as fully interchangeable. Machine TYPES with <=2 members (Grinding,
    Inspection) are left unrestricted, since the scarcity there is already
    the point.

    This is also what keeps the CP-SAT model tractable: sequence-dependent
    changeover requires a pairwise disjunctive constraint between
    every pair of candidate operations on the same machine, which is
    quadratic in the candidate-pool size. Letting every Turning operation
    compete for all 4 lathes made that pool (and solve time) blow up; capping
    it to a 2-lathe "home pool" per family cuts it roughly in half while
    still leaving the solver a real choice and the shop a fallback machine.
    """
    if len(machine_ids) <= 2:
        return machine_ids
    ids = sorted(machine_ids)
    idx = PART_FAMILIES.index(family) if family in PART_FAMILIES else 0
    pool_size = max(2, len(ids) // 2)
    start = (idx * pool_size) % len(ids)
    pool = {ids[(start + k) % len(ids)] for k in range(pool_size)}
    return sorted(pool)


def _operator_capable(operator: dict, op_type: str, machine_id: str) -> bool:
    return op_type in operator["skills"] and machine_id in operator["qualified_machines"]


def build_operator_blocked_ranges(operator: dict, horizon_days: int,
                                   overlay: Optional[Overlay] = None) -> List[Tuple[int, int]]:
    """Everything OUTSIDE an operator's rostered (and non-absent) shifts is a
    blocked range, expressed the same way machine maintenance/breakdowns are -
    this lets constraints.py treat operator unavailability and machine
    unavailability with one shared mechanism (see constraints.block_resource)."""
    roster = operator.get("roster", {})
    absences = operator.get("absences", {})
    extra_abs = set(overlay.operator_extra_absences.get(operator["operator_id"], [])) if overlay else set()

    blocked = []
    for day in range(horizon_days):
        rostered_shifts = set(roster.get(str(day), roster.get(day, [])))
        abs_shifts = set(absences.get(str(day), [])) | set(absences.get(day, []))
        for shift in (1, 2):
            working = shift in rostered_shifts and shift not in abs_shifts and (day, shift) not in extra_abs
            if not working:
                blocked.append((min(buckets_for_day_shift(day, shift, include_overtime=True)),
                                 max(buckets_for_day_shift(day, shift, include_overtime=True)) + 1))
    return blocked


def build_machine_blocked_ranges(machine: dict, overlay: Optional[Overlay] = None) -> List[Tuple[int, int]]:
    ranges = []
    for w in machine.get("maintenance_windows", []):
        day = w["day_index"]
        base = day * BUCKETS_PER_DAY_WITH_OT
        start_b = base + int(round(w["start_hour"] * 4))  # 4 buckets/hour (15-min)
        end_b = base + int(round(w["end_hour"] * 4))
        ranges.append((start_b, end_b))
    if overlay:
        ranges.extend(overlay.extra_blocked_ranges.get(machine["machine_id"], []))
    return ranges


def build_solver_input(machines: List[dict], operators: List[dict], orders: List[dict],
                        changeovers: dict, overlay: Optional[Overlay] = None):
    """Returns (tasks: List[Task], order_infos: Dict[str, OrderInfo],
    machine_infos: Dict[str, MachineInfo], operator_infos: Dict[str, OperatorInfo])"""
    overlay = overlay or Overlay()

    machine_infos: Dict[str, MachineInfo] = {}
    for m in machines:
        status = overlay.machine_status_override.get(m["machine_id"], m.get("initial_status", "operational"))
        machine_infos[m["machine_id"]] = MachineInfo(
            machine_id=m["machine_id"], machine_name=m["machine_name"], machine_type=m["machine_type"],
            hourly_cost=m["hourly_cost"], overtime_cost=m["overtime_cost"],
            blocked_ranges=build_machine_blocked_ranges(m, overlay), status=status,
        )

    from config import HORIZON_DAYS
    operator_infos: Dict[str, OperatorInfo] = {}
    for o in operators:
        operator_infos[o["operator_id"]] = OperatorInfo(
            operator_id=o["operator_id"], name=o["name"], hourly_rate=o["hourly_rate"],
            overtime_rate=o["overtime_rate"],
            blocked_ranges=build_operator_blocked_ranges(o, HORIZON_DAYS, overlay),
        )

    machines_by_id = {m["machine_id"]: m for m in machines}
    operators_by_id = {o["operator_id"]: o for o in operators}

    def assignment_options_for(op_type: str, family: str) -> List[Tuple[str, str]]:
        capable_ids = [m["machine_id"] for m in machines if _machine_capable(m, op_type)]
        allowed_ids = set(restrict_machines_by_family(capable_ids, family))
        opts = []
        for m in machines:
            if m["machine_id"] not in allowed_ids:
                continue
            if machine_infos[m["machine_id"]].status == "down":
                continue
            for o in operators:
                if _operator_capable(o, op_type, m["machine_id"]):
                    opts.append((m["machine_id"], o["operator_id"]))
        return opts

    tasks: List[Task] = []
    order_infos: Dict[str, OrderInfo] = {}

    for order in orders:
        due_dt_bucket = datetime_to_bucket(_parse_dt(order["due_date"]), round_up=True)
        material_bucket = datetime_to_bucket(_parse_dt(order["material_available_date"]))
        release_bucket = datetime_to_bucket(_parse_dt(order["release_date"]))
        if order["order_id"] in overlay.material_overrides:
            material_bucket = max(material_bucket, overlay.material_overrides[order["order_id"]])
        earliest = max(release_bucket, material_bucket, overlay.min_start_bucket)

        order_infos[order["order_id"]] = OrderInfo(
            order_id=order["order_id"], customer=order["customer"], customer_tier=order["customer_tier"],
            part_family=order["part_family"], due_bucket=due_dt_bucket,
            late_penalty_per_day=order["late_penalty_per_day"], revenue_priority=order["revenue_priority"],
            order_value=order["order_value"],
        )

        min_seq = min(op["sequence"] for op in order["routing"])
        for op in order["routing"]:
            duration = minutes_to_buckets(op["quantity"] * op["minutes_per_piece"] + op["setup_minutes"])
            opts = assignment_options_for(op["operation_type"], order["part_family"])
            task = Task(
                operation_id=op["operation_id"], order_id=order["order_id"], sequence=op["sequence"],
                operation_type=op["operation_type"], quantity=op["quantity"], part_family=order["part_family"],
                duration_buckets=duration, eligible_machines=list({m for m, _ in opts}),
                assignment_options=opts, due_bucket=due_dt_bucket,
                earliest_start_bucket=earliest if op["sequence"] == min_seq else overlay.min_start_bucket,
            )
            frozen = overlay.task_assignments.get(op["operation_id"])
            if frozen and op["operation_id"] in overlay.frozen_task_ids:
                task.frozen = True
                task.frozen_machine = frozen["machine_id"]
                task.frozen_operator = frozen["operator_id"]
                task.frozen_start = frozen["start_bucket"]
                task.frozen_end = frozen["end_bucket"]
                task.duration_buckets = frozen["end_bucket"] - frozen["start_bucket"]
                task.assignment_options = [(frozen["machine_id"], frozen["operator_id"])]
                task.eligible_machines = [frozen["machine_id"]]
            tasks.append(task)
            order_infos[order["order_id"]].task_ids.append(op["operation_id"])

    # --- inject rework tasks ---
    for idx, rw in enumerate(overlay.rework_events):
        order = next((o for o in orders if o["order_id"] == rw["order_id"]), None)
        if order is None:
            continue
        ref_op = None
        if rw.get("operation_id"):
            ref_op = next((op for op in order["routing"] if op["operation_id"] == rw["operation_id"]), None)
        if ref_op is None:
            ref_op = max(order["routing"], key=lambda op: op["sequence"])
        rate = ref_op["minutes_per_piece"] * 0.6
        duration = minutes_to_buckets(rw["quantity"] * rate + ref_op["setup_minutes"])
        opts = assignment_options_for(ref_op["operation_type"], order["part_family"])
        rework_id = f"RWK-{idx+1:03d}-{ref_op['operation_id']}"
        task = Task(
            operation_id=rework_id, order_id=order["order_id"], sequence=ref_op["sequence"] + 0.5,
            operation_type=ref_op["operation_type"], quantity=rw["quantity"], part_family=order["part_family"],
            duration_buckets=duration, eligible_machines=list({m for m, _ in opts}), assignment_options=opts,
            due_bucket=order_infos[order["order_id"]].due_bucket, is_rework=True,
            earliest_start_bucket=overlay.min_start_bucket,
        )
        tasks.append(task)
        order_infos[order["order_id"]].task_ids.append(rework_id)

    return tasks, order_infos, machine_infos, operator_infos


def _parse_dt(value: str):
    from datetime import datetime
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.fromisoformat(value + "T06:00:00")
