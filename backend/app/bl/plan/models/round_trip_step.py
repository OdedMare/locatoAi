from typing import Literal

from pydantic import BaseModel, Field


class RoundTripStep(BaseModel):
    id: str
    op: Literal["round_trip"]
    input: str
    depart_at: str
    return_at: str
    entity_field: str
    time_field: str
    time_tolerance_minutes: float = Field(default=15, ge=0, le=1440)
    min_departure_distance_m: float = Field(default=100, ge=0, le=50000)
    max_return_distance_m: float = Field(default=100, ge=0, le=5000)
