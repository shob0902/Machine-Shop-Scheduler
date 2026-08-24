"""Pydantic models describing a generated schedule and its scheduled operations."""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel


class ScheduledOperation(BaseModel):
    order_id: str
    operation_id: str
    operation_type: str
    sequence: int
    machine_id: str
    operator_id: str
    quantity: int
    part_family: str
    start_bucket: int
    end_bucket: int
    start_time: str   # ISO datetime
    end_time: str      # ISO datetime
    day_index: int
    shift: int
    is_overtime: bool
    changeover_minutes_before: float = 0.0
    previous_family_on_machine: Optional[str] = None
    status: str = "planned"  # planned | in_progress | completed | frozen


class OrderCompletion(BaseModel):
    order_id: str
    customer: str
    customer_tier: str
    due_date: str
    promised_completion: str
    is_late: bool
    tardiness_hours: float
    status: str  # ON_TRACK | AT_RISK | LATE


class ScheduleResult(BaseModel):
    strategy: str
    generated_at: str
    solver_status: str
    solver_wall_time_seconds: float
    operations: List[ScheduledOperation]
    order_completions: List[OrderCompletion]
    metrics: dict
    cost_breakdown: dict
