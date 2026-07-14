"""HTTP request/response DTOs. The service tier translates these to/from
BL types — no business logic here (SRP)."""

from typing import Any, Dict, List, Literal, Optional

import geopandas as gpd
from pydantic import BaseModel, Field
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from app.bl.plan.models import GeoQueryPlan
from app.bl.query_orchestrator import QueryOutcome


class GeoJSONMultiPolygon(BaseModel):
    type: Literal["MultiPolygon"]
    coordinates: List

    def to_shapely(self) -> BaseGeometry:
        return shape(self.model_dump())


class QueryRequest(BaseModel):
    """The contract with the frontend: exactly {query, boundaries}."""

    query: str = Field(min_length=1)
    boundaries: Optional[GeoJSONMultiPolygon] = None


class ExecutePlanRequest(BaseModel):
    """Debug endpoint input: a hand-written plan (no AI involved)."""

    plan: GeoQueryPlan
    boundaries: Optional[GeoJSONMultiPolygon] = None


class SelectedLayerDto(BaseModel):
    """Agent trace: one layer the model chose (for the UI's agent panel)."""

    id: str
    name: str
    tags: List[str] = []
    description: str = ""


class QueryResponse(BaseModel):
    status: Literal["ok", "clarify", "error"]
    clarify: Optional[str] = None
    plan: Optional[GeoQueryPlan] = None
    features: Optional[Dict[str, Any]] = None  # GeoJSON FeatureCollection
    scalar_result: Optional[int] = None
    """For count plans, set alongside the geometries that were counted."""
    timing_ms: Optional[Dict[str, int]] = None
    token_usage: Optional[Dict[str, int]] = None
    selected_layers: List[SelectedLayerDto] = []
    reasoning: str = ""
    """The model's short Hebrew 'why' for its layer choice."""
    tool_calls: List[Dict[str, str]] = []
    """sample_field rounds the plan builder ran ({layer_id, field} each)."""

    @classmethod
    def from_outcome(cls, outcome: QueryOutcome) -> "QueryResponse":
        """The single BL-outcome → HTTP-response translation."""
        return cls(
            status=outcome.status,
            clarify=outcome.clarify,
            plan=outcome.plan,
            features=gdf_to_feature_collection(outcome.features),
            scalar_result=outcome.scalar_result,
            timing_ms=outcome.timing_ms,
            token_usage=outcome.token_usage,
            selected_layers=[
                SelectedLayerDto(
                    id=layer.id,
                    name=layer.name,
                    tags=layer.tags,
                    description=layer.description,
                )
                for layer in outcome.selected_layers
            ],
            reasoning=outcome.reasoning,
            tool_calls=outcome.tool_calls,
        )


def gdf_to_feature_collection(
    gdf: Optional[gpd.GeoDataFrame],
) -> Optional[Dict[str, Any]]:
    """Every GeoDataFrame column becomes a GeoJSON `properties` field
    automatically — ops that compute extra per-feature attributes (e.g.
    NearOp's `distance_to_target_m`, ops/near.py) need no DTO change,
    they just add a column."""
    if gdf is None:
        return None
    if gdf.empty:
        return {"type": "FeatureCollection", "features": []}
    return gdf.__geo_interface__
