"""Pydantic models describing customer orders and their operation routings."""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class Operation(BaseModel):
    """One step in an order's routing, e.g. Turning -> Milling -> ..."""
    operation_id: str
    order_id: str
    sequence: int
    operation_type: str  # matches config.OPERATION_TYPES
    quantity: int
    minutes_per_piece: float
    setup_minutes: float = 0.0  # fixed setup independent of changeover (machine warmup)


class Order(BaseModel):
    order_id: str
    customer: str
    customer_tier: str  # Tier-1 | Tier-2 | Tier-3
    part_family: str
    quantity: int
    release_date: str        # ISO date, when the order may start being worked
    material_available_date: str  # ISO date, first-op cannot start before this
    due_date: str             # ISO date/datetime, customer-promised delivery
    late_penalty_per_day: float
    revenue_priority: int = Field(..., ge=1, le=10, description="1=lowest, 10=highest")
    routing: List[Operation]
    inspection_probability_fail: float = Field(..., ge=0, le=1)
    order_value: float

    @property
    def num_operations(self) -> int:
        return len(self.routing)
