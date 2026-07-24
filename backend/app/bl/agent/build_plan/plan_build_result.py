from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.bl.plan.models.geo_query_plan import GeoQueryPlan


@dataclass
class PlanBuildResult:
    plan: Optional[GeoQueryPlan] = None
    clarify: Optional[str] = None
    attempts: int = 0
    token_usage: Optional[Dict[str, int]] = None
    tool_calls: List[Dict[str, str]] = field(default_factory=list)
    """Bounded sample_field and load_skill rounds requested by the model."""
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)
    """Safe raw model outputs and validation outcomes for troubleshooting."""
