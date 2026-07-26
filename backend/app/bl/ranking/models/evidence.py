from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RankingEvidence(BaseModel):
    feature_id: str
    entity: Optional[str] = None
    observed_at: Optional[datetime] = None
