"""Normalize MQS entities into schemas and GeoDataFrames."""

import json
import logging
from typing import Dict, Iterable, List, Optional, Tuple

import geopandas as gpd
from shapely import wkt
from shapely.geometry.base import BaseGeometry

from app.bl.catalog.models.layer_field import LayerField
from app.common.errors.provider_error import ProviderError
from app.common.utils.geo_utils import WGS84, empty_features_gdf


class MqsEntityMapper:
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
        LayerField(name="triangle", type="string", description="קוד מיון (Triangle classification code)", metadata_relevant=False),
        LayerField(name="clearence_level", type="string", description="רמת הסיווג/הרשאה (Clearance level)", metadata_relevant=False),
        LayerField(name="source_id", type="number", description="מזהה מערכת המקור (Source system id)", metadata_relevant=False),
        LayerField(name="date", type="date", description="תאריך ושעת הרשומה (Record date)", metadata_relevant=False),
        LayerField(name="area", type="number", description="שטח הפוליגון (Polygon area)", metadata_relevant=False),
        LayerField(name="perimeter", type="number", description="היקף הפוליגון (Polygon perimeter)", metadata_relevant=False),
    )
    _LON_RANGE = (-180.0, 180.0)
    _LAT_RANGE = (-90.0, 90.0)

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def first(self, entity: dict, keys: Tuple[str, ...]) -> Optional[object]:
        return next((entity[key] for key in keys if key in entity), None)

    def find_list(self, payload: object, keys: Tuple[str, ...]) -> Optional[List[dict]]:
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
        raw = self.first(entity, self.PROPERTY_LIST_KEYS)
        raw = self._decode_properties(raw)
        if isinstance(raw, dict):
            return self._properties_from_mapping(raw)
        if isinstance(raw, list):
            return self._properties_from_list(raw)
        return {}

    def to_record(self, entity: dict) -> Optional[Tuple[BaseGeometry, dict]]:
        geometry = self._parse_geometry(entity.get("geo"))
        return None if geometry is None else (geometry, self._attributes(entity))

    def to_gdf(
        self, layer_id: str, entities: Iterable[dict], boundary=None
    ) -> gpd.GeoDataFrame:
        records = [self.to_record(entity) for entity in entities]
        skipped = sum(record is None for record in records)
        valid = [record for record in records if record is not None]
        if boundary is not None:
            valid = [record for record in valid if record[0].intersects(boundary)]
        if skipped:
            self._logger.warning(
                "MQS layer %s skipped %d invalid geometries", layer_id, skipped
            )
        return self._records_to_gdf(valid)

    def _decode_properties(self, raw: object) -> object:
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
        attributes = self._fixed_attributes(entity)
        for key, value in self.property_attributes(entity).items():
            attributes.setdefault(key, value)
        return attributes

    def _fixed_attributes(self, entity: dict) -> dict:
        attributes = self._identity_attributes(entity)
        classification = entity.get("classification")
        if isinstance(classification, dict):
            self._copy_keys(classification, attributes, (
                "triangle", "clearence_level", "source_id",
            ))
        self._copy_keys(entity, attributes, ("date", "link"))
        geo = entity.get("geo")
        if isinstance(geo, dict):
            self._copy_keys(geo, attributes, ("area", "perimeter"))
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
            return wkt.loads(value) if isinstance(value, str) and value.strip() else None
        except Exception:
            return None

    def _records_to_gdf(
        self, records: List[Tuple[BaseGeometry, dict]]
    ) -> gpd.GeoDataFrame:
        if not records:
            return empty_features_gdf()
        geometries, attributes = zip(*records)
        gdf = gpd.GeoDataFrame(
            list(attributes), geometry=list(geometries), crs=WGS84
        )
        return self._ensure_wgs84(gdf)

    def _ensure_wgs84(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        if gdf.crs is None:
            gdf = gdf.set_crs(WGS84)
        if not self._looks_like_wgs84(gdf):
            raise ProviderError(
                f"MQS geometry coordinates {list(gdf.total_bounds)} are outside WGS84 "
                "lon/lat range — the service may be serving a projected CRS"
            )
        return gdf

    def _looks_like_wgs84(self, gdf: gpd.GeoDataFrame) -> bool:
        bounds = gdf.total_bounds
        if len(bounds) != 4 or any(value != value for value in bounds):
            return True
        min_x, min_y, max_x, max_y = bounds
        return (self._LON_RANGE[0] <= min_x <= max_x <= self._LON_RANGE[1]
                and self._LAT_RANGE[0] <= min_y <= max_y <= self._LAT_RANGE[1])

    @staticmethod
    def _dicts(values: List[object]) -> List[dict]:
        return [item for item in values if isinstance(item, dict)]
