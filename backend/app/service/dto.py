"""HTTP request/response DTOs. The service tier translates these to/from
BL types — no business logic here (SRP)."""

from typing import Any, Literal

import geopandas as gpd
from pydantic import BaseModel, Field
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from app.bl.plan.models import GeoQueryPlan


class GeoJSONMultiPolygon(BaseModel):
    type: Literal["MultiPolygon"]
    coordinates: list

    def to_shapely(self) -> BaseGeometry:
        return shape(self.model_dump())


class QueryRequest(BaseModel):
    """The contract with the frontend: exactly {query, boundaries}."""

    query: str = Field(min_length=1)
    boundaries: GeoJSONMultiPolygon | None = None


class ExecutePlanRequest(BaseModel):
    """Debug endpoint input: a hand-written plan (no AI involved)."""

    plan: GeoQueryPlan
    boundaries: GeoJSONMultiPolygon | None = None


class QueryResponse(BaseModel):
    status: Literal["ok", "clarify", "error"]
    clarify: str | None = None
    plan: GeoQueryPlan | None = None
    features: dict[str, Any] | None = None  # GeoJSON FeatureCollection
    timing_ms: dict[str, int] | None = None


def gdf_to_feature_collection(gdf: gpd.GeoDataFrame | None) -> dict[str, Any] | None:
    if gdf is None:
        return None
    if gdf.empty:
        return {"type": "FeatureCollection", "features": []}
    return gdf.__geo_interface__
