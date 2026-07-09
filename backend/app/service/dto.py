"""HTTP request/response DTOs. The service tier translates these to/from
BL types — no business logic here (SRP)."""

from typing import Any, Dict, List, Literal, Optional

import geopandas as gpd
from pydantic import BaseModel, Field
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from app.bl.plan.models import GeoQueryPlan


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


class QueryResponse(BaseModel):
    status: Literal["ok", "clarify", "error"]
    clarify: Optional[str] = None
    plan: Optional[GeoQueryPlan] = None
    features: Optional[Dict[str, Any]] = None  # GeoJSON FeatureCollection
    timing_ms: Optional[Dict[str, int]] = None


def gdf_to_feature_collection(
    gdf: Optional[gpd.GeoDataFrame],
) -> Optional[Dict[str, Any]]:
    if gdf is None:
        return None
    if gdf.empty:
        return {"type": "FeatureCollection", "features": []}
    return gdf.__geo_interface__
