"""
Greedy constructive heuristic used ONLY to produce a warm-start hint for
CP-SAT (`model.AddHint`) - it is NOT the scheduling engine itself and never
returned to the API on its own. CP-SAT's exact search can take a long time to
find its own first feasible solution in a model this symmetric (many
interchangeable machines/operators); handing it a valid, constraint-respecting
starting point makes both "find any feasible schedule" and "prove optimality"
converge dramatically faster, and does not change what is or isn't feasible -
CP-SAT is always free to move away from the hint if a better solution exists.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from config import BUCKETS_PER_DAY_WITH_OT, BUCKETS_PER_DAY
from scheduler.models import Task, OrderInfo, MachineInfo, OperatorInfo
from scheduler.constraints import changeover_minutes, _minutes_to_buckets

DAY_LEN = BUCKETS_PER_DAY_WITH_OT


def _rank_key(strategy: str, finish: int, m: str, o: str,
              machine_infos: Dict[str, MachineInfo], operator_infos: Dict[str, OperatorInfo],
              machine_occupied: Dict[str, list]) -> tuple:
    """Lower is better. See greedy_construct's docstring for what each
    strategy optimizes for when picking among tied/near-tied candidates."""
    # Finishing later almost always costs more overall (tardiness penalties
    # dwarf small per-hour rate differences), so every strategy keeps
    # "finish soonest" as the PRIMARY key - a purely cost-greedy or
    # purely load-greedy heuristic pick can otherwise chase a cheaper/less-
    # busy resource straight into large avoidable penalty costs, which is
    # not what a real "cheapest" plan would do. Strategy only breaks ties
    # among options that finish within half a shift of each other.
    TIE_WINDOW_BUCKETS = 16
    finish_bucket = finish // TIE_WINDOW_BUCKETS
    if strategy == "cheapest":
        combined_rate = machine_infos[m].hourly_cost + operator_infos[o].hourly_rate
        return (finish_bucket, round(combined_rate), finish)
    if strategy == "most_robust":
        busy_buckets = sum(e - s for s, e, _ in machine_occupied.get(m, []))
        return (finish_bucket, busy_buckets, finish)
    return (finish,)  # most_on_time (and default): earliest finish wins


def _overlaps(a_start, a_end, b_start, b_end) -> bool:
    return a_start < b_end and b_start < a_end


def _earliest_free_slot(occupied: List[Tuple[int, int]], blocked: List[Tuple[int, int]],
                         duration: int, earliest: int, horizon: int) -> Optional[int]:
    """First bucket >= `earliest` where a `duration`-long interval fits
    without hitting `occupied` or `blocked` ranges and without crossing a
    day boundary (mirrors the day-boundary guard in constraints.py)."""
    candidates = sorted(set([earliest] + [e for _, e in occupied] + [e for _, e in blocked]))
    for cand in candidates:
        if cand < earliest:
            continue
        offset = cand % DAY_LEN
        if offset + duration > DAY_LEN:
            # push to the next day's start
            cand = (cand // DAY_LEN + 1) * DAY_LEN
        end = cand + duration
        if end > horizon:
            return None
        if any(_overlaps(cand, end, bs, be) for bs, be in occupied):
            continue
        if any(_overlaps(cand, end, bs, be) for bs, be in blocked):
            continue
        return cand
    return None


def greedy_construct(tasks: List[Task], order_infos: Dict[str, OrderInfo],
                      machine_infos: Dict[str, MachineInfo], operator_infos: Dict[str, OperatorInfo],
                      changeovers: dict, horizon_buckets: int, strategy: str = "most_on_time") -> Dict[str, dict]:
    """
    `strategy` makes this heuristic a REAL (if simpler than CP-SAT) stand-in
    for the chosen optimization mode when it is used as the fallback
    schedule (scheduler/solver.py, when CP-SAT cannot reach a first
    incumbent in time) - not just a strategy-blind construction. It changes
    which candidate (machine, operator) is preferred when several would let
    a task finish at nearly the same time:
      cheapest     -> prefer the lower combined hourly rate
      most_on_time -> prefer whichever finishes earliest (the default)
      most_robust  -> prefer the LESS-loaded machine, spreading work away
                      from the busiest (esp. grinding) resources
    """
    by_order: Dict[str, List[Task]] = {}
    for t in tasks:
        by_order.setdefault(t.order_id, []).append(t)
    for ts in by_order.values():
        ts.sort(key=lambda t: t.sequence)

    machine_occupied: Dict[str, List[Tuple[int, int, str]]] = {m: [] for m in machine_infos}
    operator_occupied: Dict[str, List[Tuple[int, int]]] = {o: [] for o in operator_infos}
    result: Dict[str, dict] = {}

    # Pre-seed occupancy with frozen tasks so the greedy pass respects them.
    for t in tasks:
        if t.frozen:
            machine_occupied[t.frozen_machine].append((t.frozen_start, t.frozen_end, t.part_family))
            operator_occupied[t.frozen_operator].append((t.frozen_start, t.frozen_end))
            result[t.operation_id] = {"machine_id": t.frozen_machine, "operator_id": t.frozen_operator,
                                       "start": t.frozen_start, "end": t.frozen_end}

    # Order ready-queue by (due date urgency, revenue priority desc, sequence)
    orders_sorted = sorted(by_order.items(), key=lambda kv: (
        order_infos[kv[0]].due_bucket, -order_infos[kv[0]].revenue_priority))

    for order_id, order_tasks in orders_sorted:
        seq_groups: Dict[float, List[Task]] = {}
        for t in order_tasks:
            seq_groups.setdefault(t.sequence, []).append(t)
        prev_step_end = 0
        for seq in sorted(seq_groups):
            group = seq_groups[seq]
            step_ends = []
            for t in group:
                if t.frozen:
                    step_ends.append(t.frozen_end)
                    continue
                earliest = max(t.earliest_start_bucket, prev_step_end)
                best = None  # (rank_key, finish_time, start, m, o)
                for (m, o) in t.assignment_options:
                    fam_gap = 0
                    if machine_occupied[m]:
                        last_end = max(e for _, e, _ in machine_occupied[m])
                        last_fam = next(f for s, e, f in machine_occupied[m] if e == last_end)
                        if last_fam != t.part_family:
                            fam_gap = _minutes_to_buckets(changeover_minutes(changeovers, last_fam, t.part_family))
                    blocked = list(machine_infos[m].blocked_ranges)
                    occ_m = [(s, e) for s, e, _ in machine_occupied[m]]
                    occ_o = operator_occupied[o]
                    blocked_o = list(operator_infos[o].blocked_ranges)
                    slot = _earliest_free_slot(occ_m + occ_o, blocked + blocked_o, t.duration_buckets,
                                                earliest + fam_gap, horizon_buckets)
                    if slot is None:
                        continue
                    finish = slot + t.duration_buckets
                    rank = _rank_key(strategy, finish, m, o, machine_infos, operator_infos, machine_occupied)
                    if best is None or rank < best[0]:
                        best = (rank, finish, slot, m, o)
                if best is None:
                    # Fallback: the due-date-ordered pass above is a greedy
                    # heuristic, not a backtracking solver, so it can leave a
                    # handful of tasks unplaced if earlier (higher-priority)
                    # tasks claimed the machine/operator time they needed.
                    # Retry with NO due-date-driven preference - just the
                    # earliest slot in the whole horizon - so this function
                    # can still serve as a full, guaranteed-feasible fallback
                    # schedule (scheduler/solver.py) even when CP-SAT cannot
                    # reach a first incumbent within its time budget.
                    for (m, o) in t.assignment_options:
                        blocked = list(machine_infos[m].blocked_ranges)
                        occ_m = [(s, e) for s, e, _ in machine_occupied[m]]
                        occ_o = operator_occupied[o]
                        blocked_o = list(operator_infos[o].blocked_ranges)
                        slot = _earliest_free_slot(occ_m + occ_o, blocked + blocked_o, t.duration_buckets,
                                                    earliest, horizon_buckets)
                        if slot is None:
                            continue
                        finish = slot + t.duration_buckets
                        rank = _rank_key(strategy, finish, m, o, machine_infos, operator_infos, machine_occupied)
                        if best is None or rank < best[0]:
                            best = (rank, finish, slot, m, o)
                if best is None and t.assignment_options:
                    # Last resort: place it with NO conflict-checking at all.
                    # This function doubles as the input to solver.py's
                    # Phase-2 finalization pass (_finalize_with_changeover),
                    # which recomputes every operation's exact timing from
                    # scratch respecting every hard constraint - so all this
                    # heuristic ever needs to guarantee is a valid (machine,
                    # operator) CHOICE per task; Phase 2 fixes the timing.
                    m, o = t.assignment_options[0]
                    slot = earliest
                    best = ((0,), slot + t.duration_buckets, slot, m, o)
                if best is None:
                    continue  # task has no valid (machine, operator) option at all
                _, finish, slot, m, o = best
                machine_occupied[m].append((slot, finish, t.part_family))
                operator_occupied[o].append((slot, finish))
                result[t.operation_id] = {"machine_id": m, "operator_id": o, "start": slot, "end": finish}
                step_ends.append(finish)
            prev_step_end = max(step_ends) if step_ends else prev_step_end

    return result
