"""Map FLAPI Flow Package rows into application models."""

from datetime import datetime
from typing import List, Optional

import geopandas as gpd
from shapely import wkt

from app.bl.catalog.models.layer_field import LayerField
from app.bl.catalog.models.layer_meta import LayerMeta
from app.bl.catalog.models.layer_schema import LayerSchema
from app.common.errors.provider_error import ProviderError
from app.common.utils.geo_utils import WGS84, empty_features_gdf


class FlapiSchemaMapper:
    _LIST_KEYS = (
        "data", "Data", "results", "Results", "items", "Items",
        "entities", "Entities",
    )
    _TIME_FIELDS = ("eventTime", "arriveTime", "timestamp", "time", "datetime")
    _MAX_SAMPLES = 5
    _MAX_SAMPLE_CHARS = 80

    def records(self, payload: object) -> List[dict]:
        if isinstance(payload, list):
            return self._dicts(payload)
        if isinstance(payload, dict):
            if "geometry" in payload:
                return [payload]
            for key in self._LIST_KEYS:
                if isinstance(payload.get(key), list):
                    return self._dicts(payload[key])
        raise ProviderError("FLAPI returned an unrecognized response shape")

    def infer_schema(self, layer_id: str, rows: List[dict]) -> LayerSchema:
        fields = [self._inferred_field(name, rows) for name in self._field_names(rows)]
        temporal = self._temporal_field(fields)
        return LayerSchema(
            layer_id=layer_id, geometry_type="Point", fields=fields,
            temporal_field=temporal,
        )

    def to_gdf(self, rows: List[dict]) -> gpd.GeoDataFrame:
        parsed = [(row, self._point(row)) for row in rows]
        valid = [(row, geometry) for row, geometry in parsed if geometry is not None]
        if not valid:
            return empty_features_gdf()
        attributes = [{key: value for key, value in row.items() if key != "geometry"}
                      for row, _ in valid]
        return gpd.GeoDataFrame(
            attributes, geometry=[geometry for _, geometry in valid], crs=WGS84
        )

    @staticmethod
    def with_layer_roles(
        schema: LayerSchema, layer: LayerMeta
    ) -> LayerSchema:
        return schema.model_copy(update={
            "entity_field": layer.entity_field,
            "display_field": layer.display_field,
        })

    @staticmethod
    def _dicts(values: List[object]) -> List[dict]:
        return [item for item in values if isinstance(item, dict)]

    def _inferred_field(self, name: str, rows: List[dict]) -> LayerField:
        values = [row.get(name) for row in rows]
        return LayerField(
            name=name, type=self._field_type(name, values), samples=self._samples(values)
        )

    @staticmethod
    def _field_names(rows: List[dict]) -> List[str]:
        names: List[str] = []
        for row in rows:
            for raw_name in row:
                name = str(raw_name)
                if name != "geometry" and name not in names:
                    names.append(name)
        return names

    def _field_type(self, name: str, values: List[object]) -> str:
        present = [value for value in values if value is not None]
        if name in self._TIME_FIELDS or any(self._is_datetime(value) for value in present):
            return "date"
        if present and all(isinstance(value, bool) for value in present):
            return "boolean"
        if present and all(isinstance(value, (int, float)) and not isinstance(value, bool)
                           for value in present):
            return "number"
        return "string"

    @staticmethod
    def _is_datetime(value: object) -> bool:
        if not isinstance(value, str) or "T" not in value:
            return False
        try:
            datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            return True
        except ValueError:
            return False

    def _samples(self, values: List[object]) -> List[str]:
        present = [str(value)[:self._MAX_SAMPLE_CHARS]
                   for value in values if value is not None]
        return list(dict.fromkeys(present))[:self._MAX_SAMPLES]

    @staticmethod
    def _point(row: dict):
        raw = row.get("geometry")
        if not isinstance(raw, str):
            return None
        try:
            geometry = wkt.loads(raw)
            return geometry if geometry.geom_type == "Point" else None
        except Exception:
            return None
