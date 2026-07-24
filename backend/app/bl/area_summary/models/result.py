from datetime import datetime
from typing import List

from pydantic import BaseModel, Field

from app.bl.area_summary.models.fact import AreaSummaryFact
from app.bl.area_summary.models.layer_failure import AreaSummaryLayerFailure


class AreaSummaryResult(BaseModel):
    generated_at: datetime
    window_start: datetime
    window_end: datetime
    queried_layer_count: int
    successful_layer_count: int
    facts: List[AreaSummaryFact] = Field(default_factory=list)
    failures: List[AreaSummaryLayerFailure] = Field(default_factory=list)
