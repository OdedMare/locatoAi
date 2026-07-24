"""Map FLAPI metadata and rows into application models."""

from datetime import datetime
from typing import List, Optional

import geopandas as gpd
from shapely import wkt

from app.bl.catalog.models.layer_field import LayerField
from app.bl.catalog.models.layer_meta import LayerMeta
from app.bl.catalog.models.layer_parameter import LayerParameter
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

    def merge_schema(
        self, layer_id: str, metadata: dict, sampled: Optional[LayerSchema]
    ) -> LayerSchema:
        samples = {field.name: field for field in (sampled.fields if sampled else [])}
        declared = self.metadata_fields(metadata)
        merged = [self._merge_field(field, samples.pop(field.name, None))
                  for field in declared]
        merged.extend(samples.values())
        temporal = self._temporal_field(merged)
        return LayerSchema(
            layer_id=layer_id, geometry_type="Point", fields=merged,
            parameters=self.metadata_parameters(metadata),
            source_name=str(self._value(metadata, "Name", "name") or ""),
            source_description=str(self._value(
                metadata, "Description", "description"
            ) or ""),
            temporal_field=temporal or (sampled.temporal_field if sampled else None),
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
        prefix = "entity_field:"
        entity = next(
            (tag[len(prefix):].strip() for tag in layer.tags
             if tag.startswith(prefix) and tag[len(prefix):].strip()),
            None,
        )
        return schema.model_copy(update={"entity_field": entity})

    def metadata_fields(self, payload: dict) -> List[LayerField]:
        fields = self._value(payload, "Fields", "fields") or []
        return [
            self._metadata_field(item)
            for item in fields
            if isinstance(item, dict) and self._value(item, "Name", "name")
        ]

    def metadata_parameters(self, payload: dict) -> List[LayerParameter]:
        parameters = self._value(payload, "Parameters", "parameters") or []
        return [
            self._metadata_parameter(item)
            for item in parameters
            if isinstance(item, dict) and self._value(item, "Name", "name")
        ]

    @staticmethod
    def results_limit(metadata: dict) -> int:
        value = FlapiSchemaMapper._value(
            metadata, "ResultsLimit", "resultsLimit", "results_limit"
        )
        return value if isinstance(value, int) and value > 0 else 10000

    @staticmethod
    def deduplicate(rows: List[dict]) -> List[dict]:
        import json
        unique = {}
        for row in rows:
            key = json.dumps(row, sort_keys=True, ensure_ascii=False, default=str)
            unique.setdefault(key, row)
        return list(unique.values())

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

    def _metadata_field(self, item: dict) -> LayerField:
        description = " — ".join(
            value for value in (
                str(self._value(
                    item, "DisplayName", "displayName", "display_name"
                ) or ""),
                str(self._value(item, "Description", "description") or ""),
            ) if value
        )
        return LayerField(
            name=str(self._value(item, "Name", "name")),
            type=str(self._value(item, "Type", "type") or "string").lower(),
            description=description,
        )

    @staticmethod
    def _metadata_parameter(item: dict) -> LayerParameter:
        name = str(FlapiSchemaMapper._value(item, "Name", "name"))
        role = FlapiSchemaMapper._value(item, "Role", "role")
        dynamic = (name.casefold().endswith(":dynamic")
                   or str(role or "").casefold() == "dynamic")
        options = [] if dynamic else FlapiSchemaMapper._options(item)
        return LayerParameter(
            name=name,
            type=str(FlapiSchemaMapper._value(item, "Type", "type") or "string").lower(),
            display_name=str(FlapiSchemaMapper._value(
                item, "DisplayName", "displayName", "display_name"
            ) or ""),
            description=str(FlapiSchemaMapper._value(
                item, "Description", "description"
            ) or ""),
            required=FlapiSchemaMapper._bool_value(
                item, False, "IsRequired", "isRequired", "is_required", "required"
            ),
            single_value=FlapiSchemaMapper._bool_value(
                item, True, "IsSingleValue", "isSingleValue", "is_single_value"
            ),
            options=options, is_dynamic=dynamic,
            configured_value=None if dynamic else FlapiSchemaMapper._value(
                item, "Value", "value"
            ),
        )

    @staticmethod
    def _options(item: dict) -> List[str]:
        raw = FlapiSchemaMapper._value(item, "Options", "options") or []
        if not isinstance(raw, list):
            return []
        values = []
        for option in raw:
            value = (
                FlapiSchemaMapper._value(option, "Value", "value")
                if isinstance(option, dict)
                else option
            )
            if value not in (None, ""):
                values.append(str(value))
        return values

    @staticmethod
    def _value(item: dict, *keys: str):
        return next((item[key] for key in keys if key in item), None)

    @staticmethod
    def _bool_value(item: dict, default: bool, *keys: str) -> bool:
        value = FlapiSchemaMapper._value(item, *keys)
        if value is None:
            return default
        if isinstance(value, str):
            return value.strip().casefold() in ("true", "1", "yes")
        return bool(value)

    @staticmethod
    def _merge_field(field: LayerField, sample: Optional[LayerField]) -> LayerField:
        if sample is not None:
            field.samples = sample.samples
        return field

    def _temporal_field(self, fields: List[LayerField]) -> Optional[str]:
        names = {field.name for field in fields}
        named = next((name for name in self._TIME_FIELDS if name in names), None)
        return named or next((field.name for field in fields if field.type == "date"), None)
