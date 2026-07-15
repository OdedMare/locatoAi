from typing import List

from pydantic import BaseModel

from app.bl.plan.models.step import Step


class GeoQueryPlan(BaseModel):
    explanation: str
    steps: List[Step]
    output: str
    context_layers: List[str] = []
