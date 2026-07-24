from typing import Literal

from pydantic import BaseModel, Field


class TrajectoryRelationStep(BaseModel):
    id: str
    op: Literal["trajectory_relation"]
    input: str
    relation: Literal[
        "together",
        "same_destination",
        "same_time",
        "same_place_different_times",
    ]
    entity_field: str
    time_field: str
    max_distance_m: float = Field(default=100, gt=0, le=5000)
    time_tolerance_minutes: float = Field(default=5, ge=0, le=1440)
    max_gap_minutes: float = Field(default=15, gt=0, le=1440)
    min_duration_minutes: float = Field(default=0, ge=0, le=10080)
    min_time_separation_minutes: float = Field(default=15, gt=0, le=525600)
    min_movement_distance_m: float = Field(default=50, ge=0, le=50000)
