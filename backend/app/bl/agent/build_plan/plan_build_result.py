from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.bl.plan.models.geo_query_plan import GeoQueryPlan


@dataclass
class PlanBuildResult:
    plan: Optional[GeoQueryPlan] = None
    clarify: Optional[str] = None
    attempts: int = 0
    token_usage: Optional[Dict[str, int]] = None
    tool_calls: List[Dict[str, str]] = field(default_factory=list)
    """sample_field rounds the model requested ({layer_id, field} each)."""
