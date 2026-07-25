"""Parse MQS input and map MQS output."""

import json
import logging
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import geopandas as gpd
from shapely import wkt
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry

from app.bl.catalog.models.layer_field import LayerField
from app.bl.catalog.models.layer_meta import LayerMeta
from app.bl.catalog.models.layer_schema import LayerSchema
from app.common.errors.provider_error import ProviderError
from app.common.utils.geo_utils import WGS84, empty_features_gdf


class MqsMapper:
    """Own MQS source, request-filter, entity, and schema shapes."""

    ENTITY_ID_KEYS = ("id", "entityId", "entity_id", "Id")
    PROPERTY_LIST_KEYS = (
        "property_list", "PropertiesList", "PropertyList", "Property_List",
        "properties_list", "Properties", "properties",
    )
    _PROPERTY_NAME_KEYS = (
        "name", "Name", "key", "Key", "field", "fieldName", "FieldName",
        "field_name", "propertyName", "PropertyName", "property_name",
    )
    _PROPERTY_VALUE_KEYS = (
        "value", "Value", "fieldValue", "FieldValue", "field_value",
        "propertyValue", "PropertyValue", "property_value", "displayValue",
        "DisplayValue", "display_value",
    )
    FIXED_FIELDS = (
        LayerField(
            name="triangle", type="string",
            description="קוד מיון (Triangle classification code)",
            metadata_relevant=False),
        LayerField(
            name="clearence_level", type="string",
            description="רמת הסיווג/הרשאה (Clearance level)",
            metadata_relevant=False),
        LayerField(
            name="source_id", type="number",
            description="מזהה מערכת המקור (Source system id)",
            metadata_relevant=False),
        LayerField(
            name="date", type="date",
            description="תאריך ושעת הרשומה (Record date)",
            metadata_relevant=False),
        LayerField(
            name="area", type="number",
            description="שטח הפוליגון (Polygon area)",
            metadata_relevant=False),
        LayerField(
            name="perimeter", type="number",
            description="היקף הפוליגון (Polygon perimeter)",
            metadata_relevant=False),
    )

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    @staticmethod
    def layer_id(layer: LayerMeta) -> str:
        ignored = {"entities", "layers", "moriaproject"}
        segments = [
            part for part in layer.source_url.strip().split("/")
            if part and part.lower() not in ignored
        ]
        if segments:
            return segments[-1]
        raise ProviderError(
            "Layer %s has no MQS layer id in its source_url (%r) — "
            "expected mqs://layer/<id>" % (
                layer.id, layer.source_url,
            )
        )

    def filter_body(
        self, geometry: Optional[BaseGeometry],
        attribute_filters: Optional[Sequence[Tuple[str, str]]],
    ) -> dict:
        filters = {}
        if geometry is not None:
            filters["complex_operators"] = self._geometry_filter(geometry)
        if attribute_filters:
            filters["simple_operators"] = {"match": {
                field: {"type": "IN", "values": [value]}
                for field, value in attribute_filters
            }}
        return {"filter": filters}

    @staticmethod
    def split(geometry: BaseGeometry) -> List[BaseGeometry]:
        min_x, min_y, max_x, max_y = geometry.bounds
        if min_x == max_x or min_y == max_y:
            return [geometry]
        middle_x, middle_y = (min_x + max_x) / 2, (min_y + max_y) / 2
        cells = (
            box(min_x, min_y, middle_x, middle_y),
            box(middle_x, min_y, max_x, middle_y),
            box(min_x, middle_y, middle_x, max_y),
            box(middle_x, middle_y, max_x, max_y),
        )
        chunks = [geometry.intersection(cell) for cell in cells]
        return [item for item in chunks if not item.is_empty and item.area > 0]

    def schema(
        self, layer: LayerMeta, layer_id: str, entities: Iterable[dict],
    ) -> LayerSchema:
        dynamic: Dict[str, LayerField] = {}
        for entity in entities:
            for name, value in self.property_attributes(entity).items():
                self._add_sample(dynamic, name, value)
        self._logger.info(
            "MQS schema layer=%s dynamic_fields=%d names=%s",
            layer_id, len(dynamic), list(dynamic),
        )
        return LayerSchema(
            layer_id=layer.id, geometry_type="Polygon",
            fields=list(self.FIXED_FIELDS) + list(dynamic.values()),
            entity_field=layer.entity_field,
            temporal_field=self._temporal_field(layer),
            display_field=layer.display_field,
        )

    @staticmethod
    def first(entity: dict, keys: Tuple[str, ...]) -> Optional[object]:
        return next((entity[key] for key in keys if key in entity), None)

    def find_list(
        self, payload: object, keys: Tuple[str, ...],
    ) -> Optional[List[dict]]:
        if isinstance(payload, list):
            return self._dicts(payload)
        if isinstance(payload, dict):
            for key in keys:
                if isinstance(payload.get(key), list):
                    return self._dicts(payload[key])
        return None

    def entity_id(self, entity: dict) -> Optional[str]:
        exclusive_id = entity.get("exclusive_id")
        source = exclusive_id if isinstance(exclusive_id, dict) else entity
        value = self.first(source, self.ENTITY_ID_KEYS)
        return str(value) if value is not None else None

    def property_attributes(self, entity: dict) -> Dict[str, object]:
        raw = self._decode_properties(
            self.first(entity, self.PROPERTY_LIST_KEYS)
        )
        if isinstance(raw, dict):
            return self._properties_from_mapping(raw)
        if isinstance(raw, list):
            return self._properties_from_list(raw)
        return {}

    def to_record(self, entity: dict) -> Optional[Tuple[BaseGeometry, dict]]:
        geometry = self._parse_geometry(entity.get("geo"))
        return None if geometry is None else (geometry, self._attributes(entity))

    def to_gdf(
        self, layer_id: str, entities: Iterable[dict], boundary=None,
    ) -> gpd.GeoDataFrame:
        records = [self.to_record(entity) for entity in entities]
        skipped = sum(record is None for record in records)
        valid = [record for record in records if record is not None]
        if boundary is not None:
            valid = [item for item in valid if item[0].intersects(boundary)]
        if skipped:
            self._logger.warning(
                "MQS layer %s skipped %d invalid geometries", layer_id, skipped
            )
        return self._records_to_gdf(valid)

    @staticmethod
    def _geometry_filter(geometry: BaseGeometry) -> dict:
        min_x, min_y, max_x, max_y = geometry.bounds
        if geometry.equals(box(min_x, min_y, max_x, max_y)):
            return {"geo_bounding_box": {"geo": {
                "type": "AND",
                "values": [{
                    "location_top_left": {"lat": max_y, "lon": min_x},
                    "location_bottom_right": {"lat": min_y, "lon": max_x},
                }],
            }}}
        return {"geo_polygon": {
            "geo": {"type": "IN", "values": [geometry.wkt]}
        }}

    @staticmethod
    def _temporal_field(layer: LayerMeta) -> Optional[str]:
        for tag in layer.tags:
            if tag == "no_temporal_field":
                return None
            if tag.startswith("temporal_field:"):
                return tag[len("temporal_field:"):].strip() or None
        return "date"

    def _add_sample(
        self, fields: Dict[str, LayerField], name: str, value: object,
    ) -> None:
        sample = str(value)[:40]
        existing = fields.get(name)
        if existing is None:
            fields[name] = LayerField(
                name=name, type=self._field_type(value), samples=[sample]
            )
        elif sample not in existing.samples and len(existing.samples) < 5:
            existing.samples.append(sample)

    @staticmethod
    def _field_type(value: object) -> str:
        numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
        return "number" if numeric else "string"

    @staticmethod
    def _decode_properties(raw: object) -> object:
        if not isinstance(raw, str):
            return raw
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def _properties_from_mapping(self, raw: dict) -> Dict[str, object]:
        nested = self.first(raw, self.PROPERTY_LIST_KEYS)
        if isinstance(nested, (dict, list)):
            return self.property_attributes({"property_list": nested})
        return {
            str(key).strip(): self._property_value(value)
            for key, value in raw.items()
            if str(key).strip() and str(key).strip() != "geometry"
        }

    def _properties_from_list(self, raw: list) -> Dict[str, object]:
        attributes: Dict[str, object] = {}
        for item in raw:
            if isinstance(item, dict):
                name, value = self._property_pair(item)
                if name and name != "geometry":
                    attributes[name] = self._property_value(value)
        return attributes

    def _property_pair(self, item: dict) -> Tuple[str, object]:
        name = self.first(item, self._PROPERTY_NAME_KEYS)
        value = self.first(item, self._PROPERTY_VALUE_KEYS)
        if name is None and len(item) == 1:
            name, value = next(iter(item.items()))
        return (str(name).strip() if name is not None else "", value)

    def _property_value(self, value: object) -> object:
        if isinstance(value, dict):
            nested = self.first(value, self._PROPERTY_VALUE_KEYS)
            if nested is not None:
                return nested
        return value

    def _attributes(self, entity: dict) -> dict:
        attributes = self._identity_attributes(entity)
        classification = entity.get("classification")
        if isinstance(classification, dict):
            self._copy_keys(
                classification, attributes,
                ("triangle", "clearence_level", "source_id"),
            )
        self._copy_keys(entity, attributes, ("date", "link"))
        geo = entity.get("geo")
        if isinstance(geo, dict):
            self._copy_keys(geo, attributes, ("area", "perimeter"))
        for key, value in self.property_attributes(entity).items():
            attributes.setdefault(key, value)
        return attributes

    def _identity_attributes(self, entity: dict) -> dict:
        entity_id = self.entity_id(entity)
        return {"id": entity_id} if entity_id is not None else {}

    @staticmethod
    def _copy_keys(source: dict, target: dict, keys: Tuple[str, ...]) -> None:
        for key in keys:
            if key in source:
                target[key] = source[key]

    @staticmethod
    def _parse_geometry(value: object) -> Optional[BaseGeometry]:
        try:
            if isinstance(value, dict):
                value = value.get("wkt") or value.get("WKT")
            return (
                wkt.loads(value)
                if isinstance(value, str) and value.strip() else None
            )
        except Exception:
            return None

    @staticmethod
    def _records_to_gdf(
        records: List[Tuple[BaseGeometry, dict]],
    ) -> gpd.GeoDataFrame:
        if not records:
            return empty_features_gdf()
        geometries, attributes = zip(*records)
        gdf = gpd.GeoDataFrame(
            list(attributes), geometry=list(geometries), crs=WGS84
        )
        bounds = gdf.total_bounds
        if (
            len(bounds) == 4 and not any(value != value for value in bounds)
            and not (
                -180 <= bounds[0] <= bounds[2] <= 180
                and -90 <= bounds[1] <= bounds[3] <= 90
            )
        ):
            raise ProviderError(
                "MQS geometry coordinates %s are outside WGS84 lon/lat range"
                % list(bounds)
            )
        return gdf

    @staticmethod
    def _dicts(values: List[object]) -> List[dict]:
        return [item for item in values if isinstance(item, dict)]
