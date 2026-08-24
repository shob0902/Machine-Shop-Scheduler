"""
Soft objectives (Section 16 "Optimization objectives") and the three
scheduling strategies (Section 21).

All strategies share the same hard-constrained feasible region built by
scheduler/constraints.py; they differ only in what linear combination of
cost/lateness/utilization terms is minimized. Every number that ends up in
the objective is explainable back to the caller via `weights_used` below - no
strategy silently "does its own thing".

Design note on cost linearity: the *objective* uses a lightweight linear
approximation of overtime cost (duration x is_overtime x an average overtime
premium, rather than the exact premium of whichever machine+operator combo
CP-SAT ultimately picks) so the model stays a plain 0/1 linear program CP-SAT
can search efficiently - see docs/scheduling-algorithm.md ("Why the objective
approximates overtime cost"). The *reported* cost breakdown shown to users
(scheduler/solver.py:_decode_cost_breakdown) is NOT an approximation: it is
computed after solving, directly from the realized machine/operator/duration
of every scheduled operation, so what supervisors see is always exact.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from ortools.sat.python import cp_model

from config import BUCKET_MINUTES, BUCKETS_PER_DAY_WITH_OT
from scheduler.constraints import ModelVars
from scheduler.models import OrderInfo, MachineInfo, OperatorInfo

STRATEGIES = ("cheapest", "most_on_time", "most_robust")

BUCKET_HOURS = BUCKET_MINUTES / 60.0
SCALE = 100  # fixed-point integer currency units (2 dp) so CP-SAT stays integer-only


@dataclass
class CommonTerms:
    completion: Dict[str, cp_model.IntVar]
    tardiness: Dict[str, cp_model.IntVar]
    is_late: Dict[str, cp_model.IntVar]
    machine_busy_buckets: Dict[str, object]
    operating_cost_expr: object
    overtime_cost_expr: object
    penalty_cost_expr: object


def build_common_terms(V: ModelVars, order_infos: Dict[str, OrderInfo],
                        machine_infos: Dict[str, MachineInfo],
                        operator_infos: Dict[str, OperatorInfo]) -> CommonTerms:
    model = V.model
    completion, tardiness, is_late = {}, {}, {}

    tasks_by_order: Dict[str, List[str]] = {}
    for tid, t in V.tasks_by_id.items():
        if tid in V.start:
            tasks_by_order.setdefault(t.order_id, []).append(tid)

    for order_id, order in order_infos.items():
        tids = tasks_by_order.get(order_id, [])
        if not tids:
            continue
        max_seq = max(V.tasks_by_id[tid].sequence for tid in tids)
        finishers = [tid for tid in tids if V.tasks_by_id[tid].sequence == max_seq]
        comp = model.NewIntVar(0, 10 ** 7, f"completion_{order_id}")
        model.AddMaxEquality(comp, [V.end[tid] for tid in finishers])
        completion[order_id] = comp

        tard = model.NewIntVar(0, 10 ** 7, f"tardiness_{order_id}")
        model.Add(tard >= comp - order.due_bucket)
        model.Add(tard >= 0)
        tardiness[order_id] = tard

        late = model.NewBoolVar(f"late_{order_id}")
        model.Add(comp > order.due_bucket).OnlyEnforceIf(late)
        model.Add(comp <= order.due_bucket).OnlyEnforceIf(late.Not())
        is_late[order_id] = late

    # --- machine busy-time (for utilization / robustness) -----------------
    machine_busy: Dict[str, object] = {}
    for mid in machine_infos:
        terms = []
        for tid, t in V.tasks_by_id.items():
            um = V.uses_machine.get(tid, {}).get(mid)
            if um is not None:
                terms.append(um * t.duration_buckets)
        machine_busy[mid] = sum(terms) if terms else 0

    # --- operating cost: exact & linear (assign * hours * regular_rate) ---
    operating_terms = []
    for tid, t in V.tasks_by_id.items():
        if tid not in V.start:
            continue
        hours = t.duration_buckets * BUCKET_HOURS
        for (m, o), a in V.assign[tid].items():
            reg_rate = machine_infos[m].hourly_cost + operator_infos[o].hourly_rate
            operating_terms.append(a * int(round(hours * reg_rate * SCALE)))
    operating_cost_expr = sum(operating_terms) if operating_terms else 0

    # --- overtime cost: linear APPROXIMATION using the shop-average premium
    # (see module docstring). Kept as `is_overtime[t] * hours * avg_premium`
    # so no per-(task, machine, operator) AND-reification is needed - that
    # reification was the single largest source of CP-SAT model blow-up
    # during development (it alone produced ~7,000 extra constraints on a
    # 211-operation dataset and pushed time-to-first-feasible past 60s).
    premiums = [(machine_infos[m].overtime_cost - machine_infos[m].hourly_cost) +
                (operator_infos[o].overtime_rate - operator_infos[o].hourly_rate)
                for m in machine_infos for o in operator_infos]
    avg_premium = sum(premiums) / len(premiums) if premiums else 0.0
    overtime_terms = []
    for tid, t in V.tasks_by_id.items():
        if tid not in V.start:
            continue
        hours = t.duration_buckets * BUCKET_HOURS
        overtime_terms.append(V.is_overtime[tid] * int(round(hours * avg_premium * SCALE)))
    overtime_cost_expr = sum(overtime_terms) if overtime_terms else 0

    # --- penalty cost: exact & linear (tardiness_buckets * penalty/bucket) -
    penalty_terms = []
    for order_id, tard in tardiness.items():
        penalty_per_bucket = order_infos[order_id].late_penalty_per_day / BUCKETS_PER_DAY_WITH_OT
        penalty_terms.append(tard * int(round(penalty_per_bucket * SCALE)))
    penalty_cost_expr = sum(penalty_terms) if penalty_terms else 0

    return CommonTerms(completion=completion, tardiness=tardiness, is_late=is_late,
                        machine_busy_buckets=machine_busy, operating_cost_expr=operating_cost_expr,
                        overtime_cost_expr=overtime_cost_expr, penalty_cost_expr=penalty_cost_expr)


@dataclass
class StrategyResult:
    objective_expr: object
    weights_used: dict
    common: CommonTerms


def build_objective(strategy: str, V: ModelVars, order_infos: Dict[str, OrderInfo],
                     machine_infos: Dict[str, MachineInfo], operator_infos: Dict[str, OperatorInfo]) -> StrategyResult:
    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown strategy '{strategy}'. Must be one of {STRATEGIES}")

    model = V.model
    common = build_common_terms(V, order_infos, machine_infos, operator_infos)
    operating_cost = common.operating_cost_expr
    overtime_cost = common.overtime_cost_expr
    penalty_cost = common.penalty_cost_expr

    weights_used = {}

    if strategy == "cheapest":
        # Strategy 1: minimize total monetary cost outright.
        objective = operating_cost + overtime_cost + penalty_cost
        weights_used = {"operating_cost": 1, "overtime_cost": 1, "penalty_cost": 1}

    elif strategy == "most_on_time":
        # Strategy 2: primarily minimize lateness (count + magnitude, with
        # extra weight for high customer-priority orders); cost only breaks
        # ties between equally-on-time schedules. CP-SAT solves a single
        # scalar objective, so "primary vs secondary" is expressed by making
        # the lateness weights large integers relative to the cost terms
        # (which are already in SCALE=100 fixed-point units) rather than by
        # a fractional cost weight - CP-SAT objectives must stay integer.
        LATE_ORDER_WEIGHT = 30_000_00   # heavy fixed penalty per late order
        TARDINESS_WEIGHT = 3_000_00     # per-bucket tardiness weight
        late_terms, tardiness_terms = [], []
        for order_id, late in common.is_late.items():
            priority = order_infos[order_id].revenue_priority
            late_terms.append(late * LATE_ORDER_WEIGHT * priority)
            tardiness_terms.append(common.tardiness[order_id] * TARDINESS_WEIGHT * priority)
        objective = sum(late_terms) + sum(tardiness_terms) + operating_cost + overtime_cost
        weights_used = {"late_order_penalty": LATE_ORDER_WEIGHT, "tardiness_weight": TARDINESS_WEIGHT,
                         "cost_tiebreak_weight": 1, "priority_multiplier": "revenue_priority (1-10)"}

    else:  # most_robust
        # Strategy 3: keep on-time performance reasonable, but explicitly
        # reward SPARE CAPACITY on the shop's bottleneck resources (esp. the
        # 2 grinding machines / 3 grinding operators - the scenario's known
        # fragile point) so the plan can absorb a breakdown without collapsing.
        grind_machines = [mid for mid, m in machine_infos.items() if m.machine_type == "Grinding"]
        peak_util = model.NewIntVar(0, 10 ** 7, "peak_machine_busy")
        for mid, busy in common.machine_busy_buckets.items():
            model.Add(peak_util >= busy)
        grind_peak = model.NewIntVar(0, 10 ** 7, "peak_grind_busy")
        for mid in grind_machines:
            model.Add(grind_peak >= common.machine_busy_buckets[mid])

        TARDINESS_WEIGHT = 8_000_00
        PEAK_UTIL_WEIGHT = 3_000_00
        GRIND_PEAK_WEIGHT = 10_000_00  # extra weight: protect the scarce grinding resource specifically
        tardiness_terms = [common.tardiness[oid] * TARDINESS_WEIGHT * order_infos[oid].revenue_priority
                            for oid in common.tardiness]
        objective = (sum(tardiness_terms) + peak_util * PEAK_UTIL_WEIGHT + grind_peak * GRIND_PEAK_WEIGHT +
                     operating_cost + overtime_cost)
        weights_used = {"tardiness_weight": TARDINESS_WEIGHT, "peak_utilization_weight": PEAK_UTIL_WEIGHT,
                         "grinding_peak_weight": GRIND_PEAK_WEIGHT, "cost_tiebreak_weight": 1}

    return StrategyResult(objective_expr=objective, weights_used=weights_used, common=common)
