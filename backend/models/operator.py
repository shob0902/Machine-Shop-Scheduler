"""Pydantic models describing shop operators and the shift roster."""
from __future__ import annotations

from typing import Dict, List
from pydantic import BaseModel, Field


class Operator(BaseModel):
    operator_id: str
    name: str
    skills: List[str] = Field(..., description="Operation types this operator is trained on")
    qualified_machines: List[str] = Field(..., description="Machine IDs this operator may run")
    available_shifts: List[int] = Field(default_factory=lambda: [1, 2])
    hourly_rate: float
    overtime_rate: float
    # roster[day_index] -> list of shifts (1, 2) the operator is rostered for.
    roster: Dict[int, List[int]] = Field(default_factory=dict)
    # ad-hoc absences applied on top of the roster: {day_index: [shift, ...]}
    absences: Dict[int, List[int]] = Field(default_factory=dict)

    def is_available(self, day_index: int, shift: int) -> bool:
        if shift not in self.available_shifts:
            return False
        rostered = shift in self.roster.get(day_index, [])
        absent = shift in self.absences.get(day_index, [])
        return rostered and not absent
