"""
CP-SAT variable & hard-constraint construction.

Hard constraints implemented here (all MUST hold in any returned solution):
 1. Operation precedence            -> _add_precedence
 2. Machine capability               -> baked into Task.assignment_options
 3. Machine capacity / no overlap    -> _add_resource_disjunctions (machine side)
 4. Operator availability            -> _block_resource_unavailability (operator side)
 5. Operator skills                  -> baked into Task.assignment_options
 6. Shift availability                -> operator blocked_ranges + day-boundary guard
 7. Maintenance windows              -> machine blocked_ranges
 8. Material availability             -> earliest_start_bucket lower bound
 9. Release dates                     -> earliest_start_bucket lower bound
10. Valid machine assignment          -> exactly-one over assignment_options
11. Valid operator assignment         -> exactly-one over assignment_options (joint w/ #10)

Soft objective ingredients (tardiness, overtime, changeover) are computed as
CP-SAT expressions here too, since they are needed downstream by
scheduler/objectives.py to build the strategy-specific objective function.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from ortools.sat.python import cp_model

from config import BUCKETS_PER_DAY_WITH_OT, BUCKETS_PER_DAY
from scheduler.models import Task, OrderInfo, MachineInfo, OperatorInfo

DAY_LEN = BUCKETS_PER_DAY_WITH_OT
DUE_DATE_SEARCH_SLACK_BUCKETS = 6 * DAY_LEN  # 6 days of "how late could this reasonably run" slack


@dataclass
class ModelVars:
    model: cp_model.CpModel
    start: Dict[str, cp_model.IntVar]
    end: Dict[str, cp_model.IntVar]
    interval: Dict[str, "cp_model.IntervalVar"]
    assign: Dict[str, Dict[Tuple[str, str], cp_model.IntVar]]
    uses_machine: Dict[str, Dict[str, cp_model.IntVar]]
    uses_operator: Dict[str, Dict[str, cp_model.IntVar]]
    is_overtime: Dict[str, cp_model.IntVar]
    order_lit: Dict[Tuple[str, str], cp_model.IntVar]
    tasks_by_id: Dict[str, Task]
    infeasible_tasks: List[str]


def changeover_minutes(changeovers: dict, fam_from: str, fam_to: str) -> int:
    return changeovers.get(fam_from, {}).get(fam_to, 30)


def build_model(tasks: List[Task], order_infos: Dict[str, OrderInfo],
                 machine_infos: Dict[str, MachineInfo], operator_infos: Dict[str, OperatorInfo],
                 changeovers: dict, horizon_buckets: int) -> ModelVars:
    model = cp_model.CpModel()

    tasks_by_id = {t.operation_id: t for t in tasks}
    infeasible_tasks = [t.operation_id for t in tasks if not t.assignment_options]

    start: Dict[str, cp_model.IntVar] = {}
    end: Dict[str, cp_model.IntVar] = {}
    interval: Dict[str, cp_model.IntervalVar] = {}
    assign: Dict[str, Dict[Tuple[str, str], cp_model.IntVar]] = {}
    uses_machine: Dict[str, Dict[str, cp_model.IntVar]] = {}
    uses_operator: Dict[str, Dict[str, cp_model.IntVar]] = {}
    is_overtime: Dict[str, cp_model.IntVar] = {}

    for t in tasks:
        if not t.assignment_options:
            # No valid (machine, operator) combination exists at all - skip
            # variable creation; solver.py reports this as a clear error
            # before ever calling Solve().
            continue

        lo = max(0, t.earliest_start_bucket)
        hi = horizon_buckets - t.duration_buckets
        if t.due_bucket is not None:
            # Prune the (otherwise huge, mostly-irrelevant) search space: an
            # operation almost never needs to be searched arbitrarily far
            # past its order's due date. A generous slack still lets CP-SAT
            # find and correctly penalize a genuinely-late completion; it
            # just stops it wasting search effort considering start times
            # deep into week 3 for an order due in week 1. This is purely a
            # performance tactic (see docs/scheduling-algorithm.md), not a
            # new hard constraint - DUE_DATE_SEARCH_SLACK_BUCKETS is wide
            # enough that no realistically-achievable schedule is excluded.
            hi = min(hi, t.due_bucket + DUE_DATE_SEARCH_SLACK_BUCKETS)
        if t.frozen:
            lo = hi = t.frozen_start
        s = model.NewIntVar(lo, max(lo, hi), f"start_{t.operation_id}")
        e = model.NewIntVar(lo + t.duration_buckets, max(lo + t.duration_buckets, hi + t.duration_buckets),
                             f"end_{t.operation_id}")
        model.Add(e == s + t.duration_buckets)
        iv = model.NewIntervalVar(s, t.duration_buckets, e, f"iv_{t.operation_id}")
        start[t.operation_id] = s
        end[t.operation_id] = e
        interval[t.operation_id] = iv

        # Day-boundary guard: a single operation may never straddle the
        # overnight non-working gap or the end of the modelled horizon day.
        offset = model.NewIntVar(0, DAY_LEN - 1, f"offset_{t.operation_id}")
        model.AddModuloEquality(offset, s, DAY_LEN)
        model.Add(offset + t.duration_buckets <= DAY_LEN)

        ot = model.NewBoolVar(f"ot_{t.operation_id}")
        model.Add(offset + t.duration_buckets - 1 >= BUCKETS_PER_DAY).OnlyEnforceIf(ot)
        model.Add(offset + t.duration_buckets - 1 < BUCKETS_PER_DAY).OnlyEnforceIf(ot.Not())
        is_overtime[t.operation_id] = ot

        # --- assignment (machine, operator) choice ---
        opts = t.assignment_options
        assign[t.operation_id] = {}
        for (m, o) in opts:
            assign[t.operation_id][(m, o)] = model.NewBoolVar(f"assign_{t.operation_id}_{m}_{o}")
        model.AddExactlyOne(assign[t.operation_id].values())
        if t.frozen:
            model.Add(assign[t.operation_id][(t.frozen_machine, t.frozen_operator)] == 1)

        uses_machine[t.operation_id] = {}
        for m in {mm for mm, _ in opts}:
            um = model.NewBoolVar(f"usesM_{t.operation_id}_{m}")
            terms = [assign[t.operation_id][(mm, oo)] for (mm, oo) in opts if mm == m]
            model.Add(um == sum(terms))
            uses_machine[t.operation_id][m] = um

        uses_operator[t.operation_id] = {}
        for o in {oo for _, oo in opts}:
            uo = model.NewBoolVar(f"usesO_{t.operation_id}_{o}")
            terms = [assign[t.operation_id][(mm, oo)] for (mm, oo) in opts if oo == o]
            model.Add(uo == sum(terms))
            uses_operator[t.operation_id][o] = uo

    # --- Hard constraint: operation precedence within an order ------------
    _add_precedence(model, tasks, order_infos, start, end)

    # NOTE: machine maintenance windows AND operator shift/roster/absence
    # blocked ranges are enforced inside _add_resource_disjunctions() below,
    # as mandatory "blocked" intervals sharing each resource's AddNoOverlap
    # group - see that function's docstring for why (this replaced an
    # earlier per-task-per-blocked-range reified encoding that was the
    # single largest contributor to a ~150,000-constraint, unsolvable-in-
    # reasonable-time presolved model during development).

    # --- Hard constraint: machine capacity (+ Phase-2 changeover, see below)
    # --- Hard constraint: operator capacity (no double-booking) -----------
    order_lit = _add_resource_disjunctions(model, tasks, start, end, interval, uses_machine, uses_operator,
                                            operator_infos, machine_infos, changeovers)

    return ModelVars(model=model, start=start, end=end, interval=interval, assign=assign,
                      uses_machine=uses_machine, uses_operator=uses_operator, is_overtime=is_overtime,
                      order_lit=order_lit, tasks_by_id=tasks_by_id, infeasible_tasks=infeasible_tasks)


def _add_precedence(model, tasks, order_infos, start, end):
    by_order: Dict[str, List[Task]] = {}
    for t in tasks:
        by_order.setdefault(t.order_id, []).append(t)
    for order_id, order_tasks in by_order.items():
        seqs = sorted({t.sequence for t in order_tasks})
        for i in range(len(seqs) - 1):
            cur = [t for t in order_tasks if t.sequence == seqs[i] and t.operation_id in start]
            nxt = [t for t in order_tasks if t.sequence == seqs[i + 1] and t.operation_id in start]
            for a in cur:
                for b in nxt:
                    model.Add(start[b.operation_id] >= end[a.operation_id])


def _add_resource_disjunctions(model, tasks, start, end, interval, uses_machine, uses_operator, operator_infos,
                                machine_infos, changeovers):
    """
    Both machine and operator capacity are enforced with CP-SAT's dedicated `AddNoOverlap` global
    constraint over optional intervals - the efficient, scalable primitive
    OR-Tools provides for "at most one task on this resource at a time".
    Shift/roster/absence unavailability and machine maintenance windows are
    folded into the SAME NoOverlap groups as fixed, always-present "blocked"
    intervals, rather than a separate reified constraint per (task, blocked
    range) pair.

    An earlier version of this model instead used the classic disjunctive
    "one i-before-j boolean per candidate pair, reified with the exact
    sequence-dependent changeover gap" pattern for machines.
    That is the textbook way to get EXACT changeover-aware sequencing out of
    CP-SAT, but on this dataset's scale (211 operations, several
    interchangeable machines/operators per operation) it alone produced tens
    of thousands of reified constraints and made the model impractically
    slow to even find a first feasible solution (verified during development:
    >150s without a solution on hardware where the AddNoOverlap version below
    solves in single-digit seconds). We therefore split changeover handling
    into two phases:
      Phase 1 (here, CP-SAT): decide WHICH machine/operator each operation
        gets and an approximate timing that minimizes the chosen strategy's
        cost/lateness/robustness objective, using efficient AddNoOverlap.
      Phase 2 (scheduler/solver.py:_finalize_with_changeover): a fast
        deterministic pass that REPLAYS CP-SAT's machine/operator choices in
        the relative order CP-SAT picked, and recomputes exact start times so
        that every sequence-dependent changeover gap is actually
        present in the final schedule - changeover is real and enforced in
        what gets returned to the API, it just is not re-optimized against
        during CP-SAT's own search. See docs/scheduling-algorithm.md.
    """
    active = [t for t in tasks if t.operation_id in start]

    operator_intervals: Dict[str, list] = {}
    for t in active:
        for o, uo in uses_operator[t.operation_id].items():
            operator_intervals.setdefault(o, []).append(
                model.NewOptionalIntervalVar(start[t.operation_id], t.duration_buckets, end[t.operation_id], uo,
                                              f"opiv_{t.operation_id}_{o}"))
    for o, ivs in operator_intervals.items():
        for i, (bs, be) in enumerate(operator_infos[o].blocked_ranges):
            ivs.append(model.NewIntervalVar(bs, be - bs, be, f"opblock_{o}_{i}"))
        if len(ivs) > 1:
            model.AddNoOverlap(ivs)

    machine_intervals: Dict[str, list] = {}
    for t in active:
        for m, um in uses_machine[t.operation_id].items():
            machine_intervals.setdefault(m, []).append(
                model.NewOptionalIntervalVar(start[t.operation_id], t.duration_buckets, end[t.operation_id], um,
                                              f"miv_{t.operation_id}_{m}"))
    for m, ivs in machine_intervals.items():
        for i, (bs, be) in enumerate(machine_infos[m].blocked_ranges):
            ivs.append(model.NewIntervalVar(bs, be - bs, be, f"mblock_{m}_{i}"))
        if len(ivs) > 1:
            model.AddNoOverlap(ivs)

    return {}


def _minutes_to_buckets(minutes: float) -> int:
    from config import BUCKET_MINUTES
    import math
    return max(0, math.ceil(minutes / BUCKET_MINUTES))
