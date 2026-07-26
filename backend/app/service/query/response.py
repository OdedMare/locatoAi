from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel

from app.bl.plan.models.geo_query_plan import GeoQueryPlan
from app.bl.query_orchestrator.query_outcome import QueryOutcome
from app.service.query.selected_layer import SelectedLayerDto
from app.service.shared.gdf_to_feature_collection import gdf_to_feature_collection


class QueryResponse(BaseModel):
    status: Literal["ok", "clarify", "error"]
    request_id: Optional[str] = None
    """Correlates UI diagnostics with console and JSONL events."""
    clarify: Optional[str] = None
    plan: Optional[GeoQueryPlan] = None
    features: Optional[Dict[str, Any]] = None  # GeoJSON FeatureCollection
    scalar_result: Optional[int] = None
    """For count plans, set while features is null."""
    display_field: Optional[str] = None
    timing_ms: Optional[Dict[str, int]] = None
    token_usage: Optional[Dict[str, int]] = None
    selected_layers: List[SelectedLayerDto] = []
    reasoning: str = ""
    """The model's short Hebrew 'why' for its layer choice."""
    tool_calls: List[Dict[str, str]] = []
    """Bounded sample_field and load_skill rounds used while planning."""
    pipeline_trace: List[Dict[str, Any]] = []
    """Structured, user-visible record of pipeline stages and execution."""

    @classmethod
    def from_outcome(cls, outcome: QueryOutcome) -> "QueryResponse":
        return cls(
            status=outcome.status,
            clarify=outcome.clarify,
            plan=outcome.plan,
            features=gdf_to_feature_collection(outcome.features),
            scalar_result=outcome.scalar_result,
            display_field=outcome.display_field,
            timing_ms=outcome.timing_ms,
            token_usage=outcome.token_usage,
            selected_layers=cls._selected_layers(outcome),
            reasoning=outcome.reasoning,
            tool_calls=outcome.tool_calls,
            pipeline_trace=outcome.pipeline_trace,
        )

    @staticmethod
    def _selected_layers(outcome: QueryOutcome) -> List[SelectedLayerDto]:
        return [
            SelectedLayerDto(
                id=layer.id, name=layer.name, tags=layer.tags,
                description=layer.description,
                entity_field=layer.entity_field,
                display_field=layer.display_field,
                profiles=layer.profiles,
            )
            for layer in outcome.selected_layers
        ]
