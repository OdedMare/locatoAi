import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Union
from urllib.parse import urlparse

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

from app.bl.ports.layer_field import LayerField
from app.bl.ports.layer_meta import LayerMeta
from app.bl.ports.layer_schema import LayerSchema
from app.common.geo import WGS84, empty_features_gdf

OFFSET_HOURS_FIELD = "timestamp_offset_hours"
_TYPES = {str: "string", int: "number", float: "number", bool: "boolean"}


def _samples(features: list, name: str, limit: int = 5) -> list:
    values = [str(item.get("properties", {}).get(name))[:40] for item in features]
    return list(dict.fromkeys(value for value in values if value != "None"))[:limit]


class MockGisProvider:
    def __init__(self, data_dir: Union[str, Path]):
        self._data_dir = Path(data_dir)

    def _path(self, layer: LayerMeta) -> Path:
        slug = urlparse(layer.source_url).path.rstrip("/").rsplit("/", 1)[-1]
        return self._data_dir / f"{slug}.geojson"

    def _collection(self, layer: LayerMeta) -> dict:
        path = self._path(layer)
        return json.loads(path.read_text()) if path.exists() else {"features": []}

    def describe_schema(self, layer: LayerMeta) -> LayerSchema:
        features = self._collection(layer)["features"]
        if not features:
            return LayerSchema(layer_id=layer.id, geometry_type="unknown", fields=[])
        properties = features[0].get("properties", {})
        fields = self._fields(features, properties)
        temporal = "timestamp" if OFFSET_HOURS_FIELD in properties else None
        geometry_type = features[0].get("geometry", {}).get("type", "unknown")
        return LayerSchema(layer_id=layer.id, geometry_type=geometry_type,
                           fields=fields, temporal_field=temporal)

    def _fields(self, features: list, properties: dict) -> list:
        fields = []
        for name, value in properties.items():
            field_name = "timestamp" if name == OFFSET_HOURS_FIELD else name
            field_type = "string" if name == OFFSET_HOURS_FIELD else _TYPES.get(type(value), "string")
            fields.append(LayerField(name=field_name, type=field_type,
                                     samples=_samples(features, name)))
        return fields

    def sample_field_values(self, layer: LayerMeta, field: str, limit: int = 20) -> list:
        return _samples(self._collection(layer)["features"], field, limit)

    def fetch_features(self, layer: LayerMeta, now: Optional[datetime] = None,
                       geometry: Optional[BaseGeometry] = None,
                       limit: Optional[int] = None) -> gpd.GeoDataFrame:
        path = self._path(layer)
        if not path.exists():
            return empty_features_gdf()
        result = gpd.read_file(path)
        result = result.set_crs(WGS84) if result.crs is None else result
        result = result[result.geometry.intersects(geometry)] if geometry is not None else result
        result = result.iloc[:limit] if limit is not None else result
        return self._with_timestamps(result, now)

    def _with_timestamps(self, result: gpd.GeoDataFrame,
                         now: Optional[datetime]) -> gpd.GeoDataFrame:
        if OFFSET_HOURS_FIELD not in result.columns:
            return result
        base = now or datetime.now(timezone.utc)
        result["timestamp"] = result[OFFSET_HOURS_FIELD].map(
            lambda hours: (base + timedelta(hours=float(hours))).isoformat())
        return result.drop(columns=[OFFSET_HOURS_FIELD])
