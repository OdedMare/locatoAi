from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import geopandas as gpd

from app.bl.plan.models.geo_query_plan import GeoQueryPlan
from app.bl.ports.layer_meta import LayerMeta


@dataclass
class QueryOutcome:
    status: str  # "ok" | "clarify" | "error"
    clarify: Optional[str] = None
    plan: Optional[GeoQueryPlan] = None
    features: Optional[gpd.GeoDataFrame] = None
    scalar_result: Optional[int] = None
    """For count plans, set alongside the geometries that were counted."""
    timing_ms: Optional[Dict[str, int]] = None
    token_usage: Optional[Dict[str, int]] = None
    # Agent trace — what the model chose and why (the UI's "thinking" view).
    selected_layers: List[LayerMeta] = field(default_factory=list)
    reasoning: str = ""
    tool_calls: List[Dict[str, str]] = field(default_factory=list)
    """sample_field rounds the plan builder ran ({layer_id, field} each)."""
    pipeline_trace: List[Dict[str, Any]] = field(default_factory=list)
    """User-visible operational trace; never private model chain-of-thought."""
