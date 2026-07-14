"""Mock ArcGIS provider: serves layers from local GeoJSON files.

TEST FIXTURE ONLY — not registered in production (see app/main.py, which
wires only the real 'mqs' provider). Used exclusively by tests/conftest.py
to exercise the executor/agent without a live MQS instance or Postgres.

The catalog's source_url last path segment picks the file, e.g.
https://provider.example/schools → data/schools.geojson. Layers without
a data file return an empty collection — the contract still holds.

Implements the same bl.ports.Provider protocol as the real MQS adapter
(dal/providers/mqs.py) — any Provider drops in per LSP.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Union
from urllib.parse import urlparse

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

from app.bl.ports import LayerField, LayerMeta, LayerSchema
from app.common.geo import WGS84, empty_features_gdf

# Mock temporal layers carry this property; the provider converts it to a
# concrete ISO timestamp relative to `now` so "yesterday" queries always
# have data. Tests freeze `now` for determinism.
OFFSET_HOURS_FIELD = "timestamp_offset_hours"

_PYTHON_TO_SCHEMA_TYPE = {str: "string", int: "number", float: "number", bool: "boolean"}

_MAX_SAMPLES = 5
_MAX_SAMPLE_CHARS = 40


def _sample_values(features: list, field_name: str, limit: int = _MAX_SAMPLES) -> list:
    """Up to N distinct values for a field (truncated — untrusted text)."""
    seen = []
    for feature in features:
        value = feature.get("properties", {}).get(field_name)
        if value is None:
            continue
        text = str(value)[:_MAX_SAMPLE_CHARS]
        if text not in seen:
            seen.append(text)
        if len(seen) >= limit:
            break
    return seen


class MockArcgisProvider:
    def __init__(self, data_dir: Union[str, Path]):
        self._data_dir = Path(data_dir)

    def _file_for(self, layer: LayerMeta) -> Path:
        slug = urlparse(layer.source_url).path.rstrip("/").rsplit("/", 1)[-1]
        return self._data_dir / f"{slug}.geojson"

    def describe_schema(self, layer: LayerMeta) -> LayerSchema:
        path = self._file_for(layer)
        if not path.exists():
            return LayerSchema(layer_id=layer.id, geometry_type="unknown", fields=[])

        collection = json.loads(path.read_text(encoding="utf-8"))
        features = collection.get("features", [])
        if not features:
            return LayerSchema(layer_id=layer.id, geometry_type="unknown", fields=[])

        first = features[0]
        fields = []
        temporal_field = None
        for name, value in first.get("properties", {}).items():
            if name == OFFSET_HOURS_FIELD:
                temporal_field = "timestamp"
                fields.append(
                    LayerField(name="timestamp", type="string",
                               description="ISO 8601 event time")
                )
                continue
            fields.append(
                LayerField(
                    name=name,
                    type=_PYTHON_TO_SCHEMA_TYPE.get(type(value), "string"),
                    samples=_sample_values(features, name),
                )
            )
        return LayerSchema(
            layer_id=layer.id,
            temporal_field=temporal_field,
            geometry_type=first.get("geometry", {}).get("type", "unknown"),
            fields=fields,
        )

    def sample_field_values(
        self, layer: LayerMeta, field: str, limit: int = 20
    ) -> list:
        """Distinct values of one field, for the agent's sample_field tool."""
        path = self._file_for(layer)
        if not path.exists():
            return []
        collection = json.loads(path.read_text(encoding="utf-8"))
        return _sample_values(collection.get("features", []), field, limit=limit)

    def fetch_features(
        self,
        layer: LayerMeta,
        now: Optional[datetime] = None,
        geometry: Optional[BaseGeometry] = None,
        limit: Optional[int] = None,
    ) -> gpd.GeoDataFrame:
        path = self._file_for(layer)
        if not path.exists():
            return empty_features_gdf()

        gdf = gpd.read_file(path)
        if gdf.crs is None:
            gdf = gdf.set_crs(WGS84)
        if geometry is not None:
            gdf = gdf[gdf.geometry.intersects(geometry)]
        if limit is not None:
            gdf = gdf.iloc[:limit]

        if OFFSET_HOURS_FIELD in gdf.columns:
            base = now or datetime.now(timezone.utc)
            gdf["timestamp"] = gdf[OFFSET_HOURS_FIELD].map(
                lambda hours: (base + timedelta(hours=float(hours))).isoformat()
            )
            gdf = gdf.drop(columns=[OFFSET_HOURS_FIELD])
        return gdf
