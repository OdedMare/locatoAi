"""Mock ArcGIS provider: serves layers from local GeoJSON files.

The catalog's source_url last path segment picks the file, e.g.
https://provider.example/schools → data/schools.geojson. Layers without
a data file return an empty collection — the contract still holds.

The real ArcGIS adapter (v0.2) replaces this class only; it implements
the same bl.ports.Provider protocol (LSP).
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import geopandas as gpd

from app.bl.ports import LayerField, LayerMeta, LayerSchema
from app.common.geo import WGS84, empty_features_gdf

# Mock temporal layers carry this property; the provider converts it to a
# concrete ISO timestamp relative to `now` so "yesterday" queries always
# have data. Tests freeze `now` for determinism.
OFFSET_HOURS_FIELD = "timestamp_offset_hours"

_PYTHON_TO_SCHEMA_TYPE = {str: "string", int: "number", float: "number", bool: "boolean"}


class MockArcgisProvider:
    def __init__(self, data_dir: str | Path):
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
        fields = [
            LayerField(
                name="timestamp" if name == OFFSET_HOURS_FIELD else name,
                type="string" if name == OFFSET_HOURS_FIELD
                else _PYTHON_TO_SCHEMA_TYPE.get(type(value), "string"),
            )
            for name, value in first.get("properties", {}).items()
        ]
        return LayerSchema(
            layer_id=layer.id,
            geometry_type=first.get("geometry", {}).get("type", "unknown"),
            fields=fields,
        )

    def fetch_features(
        self, layer: LayerMeta, now: datetime | None = None
    ) -> gpd.GeoDataFrame:
        path = self._file_for(layer)
        if not path.exists():
            return empty_features_gdf()

        gdf = gpd.read_file(path)
        if gdf.crs is None:
            gdf = gdf.set_crs(WGS84)

        if OFFSET_HOURS_FIELD in gdf.columns:
            base = now or datetime.now(timezone.utc)
            gdf["timestamp"] = gdf[OFFSET_HOURS_FIELD].map(
                lambda hours: (base + timedelta(hours=float(hours))).isoformat()
            )
            gdf = gdf.drop(columns=[OFFSET_HOURS_FIELD])
        return gdf
