from typing import List, Optional

from pydantic import BaseModel, Field

from app.bl.ranking.models.evidence import RankingEvidence


class RankingContribution(BaseModel):
    """One rule's verdict on one subject feature."""

    kind: str
    rule_layer_id: str
    rule_layer_name: str
    text: str
    weight: float
    raw_score: float
    weighted_score: float
    matched: bool = True
    measured_distance_m: Optional[float] = None
    matched_count: Optional[int] = None
    evidence: List[RankingEvidence] = Field(default_factory=list)
