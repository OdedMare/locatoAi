"""Shared GeoJSON MultiPolygon request model."""

from typing import List, Literal

from pydantic import BaseModel
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry


class GeoJSONMultiPolygon(BaseModel):
    type: Literal["MultiPolygon"]
    coordinates: List

    def to_shapely(self) -> BaseGeometry:
        return shape(self.model_dump())
