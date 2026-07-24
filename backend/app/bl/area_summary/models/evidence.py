from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AreaSummaryEvidence(BaseModel):
    feature_id: str
    entity: Optional[str] = None
    observed_at: Optional[datetime] = None
