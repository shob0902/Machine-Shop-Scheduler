"""Pydantic models describing shop machines, maintenance windows and breakdowns."""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class MaintenanceWindow(BaseModel):
    """A planned maintenance window for one machine (Section 12)."""
    machine_id: str
    day_index: int = Field(..., description="0-based day offset from schedule start")
    start_hour: float = Field(..., description="Hour of day the maintenance starts (0-24)")
    end_hour: float = Field(..., description="Hour of day the maintenance ends (0-24)")
    description: str = "Scheduled preventive maintenance"


class Breakdown(BaseModel):
    """Historical breakdown record used for reliability stats (Section 13)."""
    breakdown_id: str
    machine_id: str
    start_time: str  # ISO datetime, historical (before the planning horizon)
    end_time: str
    duration_minutes: int
    failure_type: str
    severity: str  # "minor" | "major" | "critical"


class Machine(BaseModel):
    machine_id: str
    machine_name: str
    machine_type: str
    capabilities: List[str] = Field(..., description="Operation types this machine can perform")
    available_shifts: List[int] = Field(default_factory=lambda: [1, 2])
    hourly_cost: float
    overtime_cost: float
    maintenance_windows: List[MaintenanceWindow] = Field(default_factory=list)
    initial_status: str = "operational"  # operational | down | maintenance
    breakdown_history: List[Breakdown] = Field(default_factory=list)

    # --- reliability metrics, computed from breakdown_history -------------
    def reliability_metrics(self) -> dict:
        if not self.breakdown_history:
            return {
                "breakdown_count": 0,
                "total_downtime_minutes": 0,
                "avg_downtime_minutes": 0.0,
                "mtbf_hours": None,
            }
        total_downtime = sum(b.duration_minutes for b in self.breakdown_history)
        count = len(self.breakdown_history)
        # Approximate MTBF over a 180-day observation window used to generate history.
        observation_hours = 180 * 24
        mtbf_hours = round((observation_hours - total_downtime / 60) / count, 1) if count else None
        return {
            "breakdown_count": count,
            "total_downtime_minutes": total_downtime,
            "avg_downtime_minutes": round(total_downtime / count, 1),
            "mtbf_hours": mtbf_hours,
        }
