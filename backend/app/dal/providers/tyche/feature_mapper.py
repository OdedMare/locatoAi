"""Map Tyche rows to geographic features."""

import json
import logging
from typing import Dict, List, Optional

import geopandas as gpd
from shapely import wkt
from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry

from app.common.utils.geo_utils import WGS84, empty_features_gdf


class TycheFeatureMapper:
    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def to_gdf(self, rows: List[dict]) -> gpd.GeoDataFrame:
        parsed = [(row, self._parse(row.get("geometry"))) for row in rows]
        valid = [(row, geometry) for row, geometry in parsed
                 if geometry is not None and not geometry.is_empty]
        self._log_invalid_count(len(rows) - len(valid))
        if not valid:
            return empty_features_gdf()
        return self._build_gdf(valid)

    def deduplicate(self, rows: List[dict]) -> List[dict]:
        unique: Dict[str, dict] = {}
        for row in rows:
            identifier = row.get("id")
            key = self._row_key(row, identifier)
            unique.setdefault(key, row)
        return list(unique.values())

    def _parse(self, value: object) -> Optional[BaseGeometry]:
        if isinstance(value, BaseGeometry):
            return value
        if isinstance(value, dict):
            return self._from_mapping(value)
        if isinstance(value, (list, tuple)):
            return self._from_coordinates(value)
        return self._from_text(value)

    def _from_mapping(self, value: dict) -> Optional[BaseGeometry]:
        if value.get("type") == "Feature":
            return self._parse(value.get("geometry"))
        if "type" in value and "coordinates" in value:
            return self._shape(value)
        for key in ("geometry", "geo", "wkt", "WKT"):
            if key in value:
                return self._parse(value[key])
        return self._point_from_mapping(value)

    @staticmethod
    def _shape(value: dict) -> Optional[BaseGeometry]:
        try:
            return shape(value)
        except (TypeError, ValueError):
            return None

    def _point_from_mapping(self, value: dict) -> Optional[BaseGeometry]:
        lon = value.get("lon", value.get("lng", value.get("longitude")))
        lat = value.get("lat", value.get("latitude"))
        return self._point(lon, lat)

    def _from_coordinates(self, value: object) -> Optional[BaseGeometry]:
        if len(value) < 2:
            return None
        return self._point(value[0], value[1])

    @staticmethod
    def _point(lon: object, lat: object) -> Optional[BaseGeometry]:
        if isinstance(lon, (int, float)) and isinstance(lat, (int, float)):
            return Point(lon, lat)
        return None

    def _from_text(self, value: object) -> Optional[BaseGeometry]:
        if not isinstance(value, str) or not value.strip():
            return None
        text = value.strip()
        if text[0] in "[{":
            parsed = self._parse_json(text)
            if parsed is not None:
                return parsed
        return self._parse_wkt(text)

    def _parse_json(self, text: str) -> Optional[BaseGeometry]:
        try:
            return self._parse(json.loads(text))
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    @staticmethod
    def _parse_wkt(text: str) -> Optional[BaseGeometry]:
        try:
            return wkt.loads(text)
        except Exception:
            return None

    @staticmethod
    def _row_key(row: dict, identifier: object) -> str:
        if identifier is not None:
            return f"id:{identifier}"
        return json.dumps(row, ensure_ascii=False, sort_keys=True, default=str)

    def _log_invalid_count(self, count: int) -> None:
        if count:
            self._logger.warning("Tyche skipped %s rows with invalid geometry", count)

    @staticmethod
    def _build_gdf(valid: List[tuple]) -> gpd.GeoDataFrame:
        attributes = [
            {key: value for key, value in row.items() if key != "geometry"}
            for row, _ in valid
        ]
        geometries = [geometry for _, geometry in valid]
        return gpd.GeoDataFrame(attributes, geometry=geometries, crs=WGS84)
