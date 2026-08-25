"""Pydantic models describing the five disruption types."""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class MachineBreakdownEvent(BaseModel):
    disruption_type: str = "machine_breakdown"
    machine_id: str
    start_time: str  # ISO datetime within the horizon
    duration_minutes: int = Field(..., gt=0)
    reason: str = "Unplanned breakdown"


class OperatorAbsenceEvent(BaseModel):
    disruption_type: str = "operator_absence"
    operator_id: str
    day_index: int
    shift: int
    reason: str = "Absent"


class MaterialDelayEvent(BaseModel):
    disruption_type: str = "material_delay"
    order_id: str
    new_material_available_time: str  # ISO datetime
    reason: str = "Supplier delay"


class ReworkEvent(BaseModel):
    disruption_type: str = "rework"
    order_id: str
    operation_id: Optional[str] = None
    quantity: int = Field(..., gt=0)
    reason: str = "Inspection failure"


class PowerCutEvent(BaseModel):
    disruption_type: str = "power_cut"
    day_index: int
    shift: int
    duration_minutes: int
    use_generator: bool = False


class DisruptionRecord(BaseModel):
    """Envelope stored for every applied disruption, for audit/history display."""
    disruption_id: str
    disruption_type: str
    created_at: str
    payload: dict
    applied: bool = False
