from typing import Literal

from pydantic import BaseModel, Field


class OriginMovementStep(BaseModel):
    id: str
    op: Literal["origin_movement"]
    input: str
    pattern: Literal["departed", "round_trip"]
    start_at: str
    end_at: str
    entity_field: str
    time_field: str
    time_tolerance_minutes: float = Field(default=15, ge=0, le=1440)
    min_departure_distance_m: float = Field(default=100, ge=0, le=50000)
    max_return_distance_m: float = Field(default=100, ge=0, le=5000)
