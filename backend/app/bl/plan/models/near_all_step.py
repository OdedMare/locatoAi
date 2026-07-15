from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from app.bl.plan.models.proximity_target import ProximityTarget


class NearAllStep(BaseModel):
    id: str
    op: Literal["near_all"]
    input: str
    targets: List[ProximityTarget] = Field(min_length=2, max_length=5)
    distance_m: float = Field(default=300, gt=0, le=5000)
    count: Optional[int] = Field(default=None, gt=0, le=50)
