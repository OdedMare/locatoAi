from typing import List, Optional

from pydantic import BaseModel, Field

from app.bl.ranking.models.contribution import RankingContribution


class RankedFeature(BaseModel):
    """One scored subject feature, with every rule's contribution kept."""

    rank: int
    feature_id: str
    label: Optional[str] = None
    total_score: float
    max_possible_score: float
    normalized_score: float
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    contributions: List[RankingContribution] = Field(default_factory=list)
