from datetime import datetime
from typing import List

from pydantic import BaseModel, Field

from app.bl.ranking.models.layer_failure import RankingLayerFailure
from app.bl.ranking.models.ranked_feature import RankedFeature


class RankingResult(BaseModel):
    generated_at: datetime
    window_start: datetime
    window_end: datetime
    subject_layer_id: str
    subject_layer_name: str
    subject_feature_count: int
    applied_rule_count: int
    successful_rule_count: int
    max_possible_score: float
    features: List[RankedFeature] = Field(default_factory=list)
    failures: List[RankingLayerFailure] = Field(default_factory=list)
