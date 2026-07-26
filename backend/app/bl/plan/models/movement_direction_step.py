from typing import Literal

from pydantic import BaseModel, Field


class MovementDirectionStep(BaseModel):
    id: str
    op: Literal["movement_direction"]
    input: str
    direction: Literal["any", "north", "south", "east", "west"]
    entity_field: str
    time_field: str
    min_distance_m: float = Field(default=50, ge=0, le=50000)
