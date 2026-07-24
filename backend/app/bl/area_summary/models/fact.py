from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from app.bl.area_summary.models.evidence import AreaSummaryEvidence


class AreaSummaryFact(BaseModel):
    kind: Literal["count", "presence", "recommendation", "encounter"]
    layer_id: str
    layer_name: str
    text: str
    count: Optional[int] = None
    entities: List[str] = Field(default_factory=list)
    observed_at: Optional[datetime] = None
    evidence: List[AreaSummaryEvidence] = Field(default_factory=list)
