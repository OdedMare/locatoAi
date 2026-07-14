"""MQS (Moria Query Service) provider: fetches layers over the MQS REST API.

Catalog rows route here with provider='mqs'; their source_url stores the
MQS layer id as "mqs://layer/{layerId}" (base-URL-independent — the live
base URL is the mqs_base_url runtime setting, read on every call). The
last path segment is the layer id, so a bare id or a pasted full URL
also work.

Fetch strategy is fetch-all-filter-locally: per the official MoriaProject
Entities API doc, GET /MoriaProject/{id}/Entities with a required
`User_ID` header (the mqs_user_id runtime setting, sent on every MQS
request) returns the full entity array for a layer; the executor then
does spatial ops locally. The doc shows no pagination parameter, so a
single request fetches everything — _MAX_FEATURES below guards against
an unexpectedly huge response; add pagination if a live layer is ever
observed being truncated. (A separate MQS search endpoint takes a
POST {"filter": ...} body — that is a future spatial-pushdown path, not
how plain retrieval works.)

Per the doc, each entity carries exclusive_id (data_store_name/layer_id/
entity_id/history_id), classification, date (DD/MM/YYYY HH:MM:SS), link,
and geo ({"wkt": "POLYGON ((lon lat alt, ...))", "area", "perimeter"});
an observed live variant instead nests geometry under "geometry"
({"wkt", "geo_json"}) and carries attributes in properties_list — both
are handled by _entity_to_record's MQS-envelope branch. WKT coordinates
are lon/lat and assumed WGS84 (the doc says to confirm the SRID with the
service owner); if a real instance serves ITM (EPSG:2039), fix it inside
_ensure_wgs84. Adapting to other variations means adjusting
_extract_entities / _entity_to_record / _entities_path.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import geopandas as gpd
import httpx
from shapely import wkt
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from app.bl.ports import LayerField, LayerMeta, LayerSchema
from app.common.errors import ProviderError
from app.common.geo import WGS84, empty_features_gdf
from app.common.runtime_settings import RuntimeSettingsStore

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 30
_MAX_FEATURES = 50000

# Same truncation policy as the mock provider: sample values are untrusted
# text that ends up in LLM prompts.
_MAX_SAMPLES = 5
_MAX_SAMPLE_CHARS = 40

_ENTITY_LIST_KEYS = (
    "features", "Features", "entities", "Entities", "data", "Data",
    "results", "Results", "items", "Items", "layers", "Layers",
    "layers_list", "LayersList",
)
_FIELD_LIST_KEYS = (
    "fields_list", "FieldsList", "fields", "attributes", "columns", "Fields"
)
_FIELD_NAME_KEYS = (
    "name", "Name", "field", "fieldName", "field_name"
)
_FIELD_TYPE_KEYS = ("type", "Type", "dataType", "data_type", "field_type")
_FIELD_DESC_KEYS = (
    "alias", "display_name", "unclassified_description",
    "description", "Description",
)
_GEOMETRY_TYPE_KEYS = ("geometryType", "geometry_type", "geomType")
_GEOMETRY_VALUE_KEYS = ("geometry", "geo", "geom", "shape", "location")
_ENTITY_ID_KEYS = ("id", "entityId", "entity_id", "Id")

# Candidate names for a layer's event-time field, checked in order against
# the described field list (properties_list-style attributes).
_TEMPORAL_FIELD_CANDIDATES = ("timestamp", "datetime", "date", "Date", "Timestamp")

# The live entity envelope ALSO always carries a top-level "date" (see
# _entity_to_record) — a per-entity system timestamp (created/modified),
# not necessarily this layer's "event time". It's used as a fallback when
# no properties_list field matches _TEMPORAL_FIELD_CANDIDATES, since most
# layers have no better candidate. Catalog rows can opt out per layer with
# the tag "no_temporal_field", or force a specific field with a tag of the
# form "temporal_field:<name>" (checked first, before any of the above).
_ENVELOPE_TEMPORAL_FIELD = "date"
_TEMPORAL_FIELD_TAG_PREFIX = "temporal_field:"
_NO_TEMPORAL_FIELD_TAG = "no_temporal_field"


def _temporal_field_override(layer: LayerMeta) -> Tuple[bool, Optional[str]]:
    """(has_override, field_name_or_None) from the layer's tags, per the
    conventions above. has_override=False means "no opinion, use defaults"."""
    for tag in layer.tags:
        if tag == _NO_TEMPORAL_FIELD_TAG:
            return True, None
        if tag.startswith(_TEMPORAL_FIELD_TAG_PREFIX):
            return True, tag[len(_TEMPORAL_FIELD_TAG_PREFIX):].strip() or None
    return False, None

_MQS_TO_SCHEMA_TYPE = {
    "string": "string", "text": "string", "str": "string",
    "int": "number", "integer": "number", "long": "number",
    "float": "number", "double": "number", "number": "number", "decimal": "number",
    "bool": "boolean", "boolean": "boolean",
    "date": "date", "datetime": "date", "timestamp": "date",
}


# Endpoint words that may trail the layer id when a full MQS link was
# pasted/synced as source_url (e.g. the inventory's layer_entities_link
# ".../MoriaProject/110/Entities") — never a layer id themselves.
_NON_ID_TRAILING_SEGMENTS = ("entities", "layers", "moriaproject")


def mqs_layer_id(layer: LayerMeta) -> str:
    """The MQS layer id is the last non-empty path segment of source_url
    (mqs://layer/42, bare "42", https://host/MoriaProject/42/ and even a
    pasted entities link https://host/MoriaProject/42/Entities all work)."""
    segments = [
        segment
        for segment in layer.source_url.strip().split("/")
        if segment and segment.lower() not in _NON_ID_TRAILING_SEGMENTS
    ]
    if not segments:
        raise ProviderError(
            f"Layer {layer.id} has no MQS layer id in its source_url "
            f"({layer.source_url!r}) — expected mqs://layer/<id>"
        )
    return segments[-1]


def _first_key(entity: dict, keys: Tuple[str, ...]) -> Optional[object]:
    for key in keys:
        if key in entity:
            return entity[key]
    return None


def _find_entity_list(payload: object) -> Optional[List[dict]]:
    """Find a list in common MQS/ASP.NET response envelopes.

    MQS deployments do not all use the same casing and some wrap the result,
    for example ``{"data": {"items": [...]}}``.  Returning ``None`` (rather
    than ``[]``) lets inventory calls distinguish an unknown response shape
    from a valid, empty inventory.
    """
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in _ENTITY_LIST_KEYS:
            if key not in payload:
                continue
            value = payload[key]
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                nested = _find_entity_list(value)
                if nested is not None:
                    return nested
    return None


def _extract_entities(payload: object) -> List[dict]:
    """Lenient list extraction for feature/schema best-effort callers."""
    return _find_entity_list(payload) or []


def _normalize_fields(raw_fields: object) -> List[dict]:
    """Normalize MQS fields_list arrays or {field_name: metadata} maps."""
    if isinstance(raw_fields, list):
        return [field for field in raw_fields if isinstance(field, dict)]
    if not isinstance(raw_fields, dict):
        return []
    normalized = []
    for key, value in raw_fields.items():
        if isinstance(value, dict):
            field = dict(value)
            if _first_key(field, _FIELD_NAME_KEYS) in (None, ""):
                field["name"] = str(key)
        else:
            # Also accept compact maps such as {"ROAD_NAME": "string"}.
            field = {"name": str(key), "type": value}
        normalized.append(field)
    return normalized


def _parse_geometry(value: object) -> Optional[BaseGeometry]:
    try:
        if isinstance(value, dict):
            # Live MQS entities wrap both representations under geometry:
            # {"wkt": "POINT(...) ", "geo_json": "Point"}.  geo_json is
            # only the geometry type in that response, so WKT is authoritative.
            nested_wkt = value.get("wkt") or value.get("WKT")
            if isinstance(nested_wkt, str) and nested_wkt.strip():
                return wkt.loads(nested_wkt)
            return shape(value)
        if isinstance(value, str) and value.strip():
            return wkt.loads(value)
    except Exception:
        return None
    return None


def _entity_to_record(entity: dict) -> Optional[Tuple[BaseGeometry, dict]]:
    """One MQS entity → (geometry, attributes), or None if no usable geometry.

    Accepts a GeoJSON Feature ({"geometry", "properties"}) or a flat dict
    with the geometry under one of several candidate keys.
    """
    if isinstance(entity.get("properties"), dict):
        geometry = _parse_geometry(entity.get("geometry"))
        if geometry is None:
            return None
        attributes = dict(entity["properties"])
        entity_id = _first_key(entity, _ENTITY_ID_KEYS)
        if entity_id is not None and "id" not in attributes:
            attributes["id"] = entity_id
        return geometry, attributes

    # MQS envelope shape (recognized by exclusive_id / properties_list):
    # the official doc puts geometry under "geo" ({"wkt", "area",
    # "perimeter"}) with no properties_list; an observed live variant puts
    # it under "geometry" ({"wkt", "geo_json"}) with attributes in
    # properties_list. Both share exclusive_id/classification/date/link.
    if isinstance(entity.get("exclusive_id"), dict) or isinstance(
        entity.get("properties_list"), dict
    ):
        geometry = _parse_geometry(entity.get("geo") or entity.get("geometry"))
        if geometry is None:
            return None
        properties_list = entity.get("properties_list")
        attributes = dict(properties_list) if isinstance(properties_list, dict) else {}
        exclusive_id = entity.get("exclusive_id")
        if isinstance(exclusive_id, dict):
            entity_id = _first_key(exclusive_id, _ENTITY_ID_KEYS)
            if entity_id is not None and "id" not in attributes:
                attributes["id"] = entity_id
        for key in ("date", "link", "classification"):
            if key in entity and key not in attributes:
                attributes[key] = entity[key]
        geo = entity.get("geo")
        if isinstance(geo, dict):
            # area/perimeter are doc-declared per-entity floats — surface
            # them as plain attributes (units are the service's CRS units).
            for key in ("area", "perimeter"):
                if key in geo and key not in attributes:
                    attributes[key] = geo[key]
        return geometry, attributes

    geometry = None
    geometry_key = None
    for key in _GEOMETRY_VALUE_KEYS:
        if key in entity:
            geometry = _parse_geometry(entity[key])
            geometry_key = key
            if geometry is not None:
                break
    if geometry is None:
        return None
    attributes = {k: v for k, v in entity.items() if k != geometry_key}
    return geometry, attributes


def _ensure_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """MQS geo_type=GeoJSON is assumed to be WGS84. If a live instance
    turns out to serve ITM, change this to set_crs(ISRAEL_TM).to_crs(WGS84)."""
    if gdf.crs is None:
        gdf = gdf.set_crs(WGS84)
    return gdf


class MqsProvider:
    """bl.ports.Provider implementation backed by the MQS REST API."""

    def __init__(
        self,
        settings_store: RuntimeSettingsStore,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self._store = settings_store
        self._transport = transport  # tests inject httpx.MockTransport

    # -- HTTP plumbing -----------------------------------------------------

    def _base_url(self) -> str:
        base_url = self._store.get().mqs_base_url
        if not base_url:
            raise ProviderError(
                "MQS base URL is not configured — set mqs_base_url in the "
                "settings panel"
            )
        return base_url

    def _headers(self) -> Dict[str, str]:
        # The official Entities doc marks User_ID as a required header
        # (example value "tt/T"). It is deployment-specific, so it comes
        # from the mqs_user_id runtime setting; when unset, no header is
        # sent and an instance that enforces it will reject the request —
        # the 4xx surfaces through ProviderError below.
        user_id = self._store.get().mqs_user_id
        return {"User_ID": user_id} if user_id else {}

    def _get_json(self, path: str, params: Optional[dict] = None) -> object:
        base_url = self._base_url()
        try:
            with httpx.Client(
                base_url=base_url,
                timeout=_TIMEOUT_SECONDS,
                transport=self._transport,
                headers=self._headers(),
            ) as client:
                response = client.get(path, params=params)
                # The MQS doc recommends logging request URL + status for
                # debugging; the full URL shows exactly how mqs_base_url
                # and the layer path were joined.
                logger.info("MQS GET %s -> %s", response.request.url,
                            response.status_code)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"MQS request failed ({path}): {exc}")
        except ValueError as exc:
            raise ProviderError(f"MQS returned invalid JSON ({path}): {exc}")

    def _entities_path(self, layer_id: str) -> str:
        # Official doc: GET /MoriaProject/{layer_id}/Entities returns the
        # full entity array — no query params, no request body, no
        # pagination parameter documented. One request fetches everything
        # (fetch-all-filter-locally); _MAX_FEATURES guards the size.
        return f"/MoriaProject/{layer_id}/Entities"

    # -- Provider protocol ---------------------------------------------------

    def describe_schema(self, layer: LayerMeta) -> LayerSchema:
        layer_id = mqs_layer_id(layer)
        payload = self._get_json(f"/MoriaProject/Layers/{layer_id}")
        if not isinstance(payload, dict):
            return LayerSchema(layer_id=layer.id, geometry_type="unknown", fields=[])

        samples = self._value_list(layer_id)
        fields = []
        raw_fields = _first_key(payload, _FIELD_LIST_KEYS)
        for raw in _normalize_fields(raw_fields):
            name = _first_key(raw, _FIELD_NAME_KEYS)
            if not isinstance(name, str) or not name:
                continue
            raw_type = _first_key(raw, _FIELD_TYPE_KEYS)
            field_type = _MQS_TO_SCHEMA_TYPE.get(
                str(raw_type).lower() if raw_type is not None else "", "string"
            )
            description = _first_key(raw, _FIELD_DESC_KEYS)
            fields.append(
                LayerField(
                    name=name,
                    type=field_type,
                    description=description if isinstance(description, str) else "",
                    samples=samples.get(name, [])[:_MAX_SAMPLES],
                )
            )

        geometry_type = _first_key(payload, _GEOMETRY_TYPE_KEYS)
        has_override, temporal_field = _temporal_field_override(layer)
        if not has_override:
            field_names = {f.name for f in fields}
            temporal_field = next(
                (c for c in _TEMPORAL_FIELD_CANDIDATES if c in field_names),
                _ENVELOPE_TEMPORAL_FIELD,
            )
        return LayerSchema(
            layer_id=layer.id,  # the catalog id, not the MQS id
            geometry_type=geometry_type if isinstance(geometry_type, str) else "unknown",
            fields=fields,
            temporal_field=temporal_field,
        )

    def fetch_features(
        self, layer: LayerMeta, now: Optional[datetime] = None
    ) -> gpd.GeoDataFrame:
        # `now` is part of the Provider protocol (mock temporal synthesis);
        # MQS serves real data, so it is ignored.
        layer_id = mqs_layer_id(layer)
        entities = _extract_entities(self._get_json(self._entities_path(layer_id)))
        if len(entities) >= _MAX_FEATURES:
            raise ProviderError(
                f"MQS layer {layer_id} returned {len(entities)} entities, at "
                f"or above the {_MAX_FEATURES} feature limit — narrow the "
                "layer or raise the cap"
            )

        geometries: List[BaseGeometry] = []
        attribute_rows: List[dict] = []
        skipped = 0
        for entity in entities:
            record = _entity_to_record(entity)
            if record is None:
                skipped += 1
                continue
            geometries.append(record[0])
            attribute_rows.append(record[1])
        if skipped:
            logger.warning(
                "MQS layer %s: skipped %d of %d entities without parseable "
                "geometry", layer_id, skipped, len(entities),
            )
        if not geometries:
            return empty_features_gdf()
        gdf = gpd.GeoDataFrame(attribute_rows, geometry=geometries, crs=WGS84)
        return _ensure_wgs84(gdf)

    def sample_field_values(
        self, layer: LayerMeta, field: str, limit: int = 20
    ) -> List[str]:
        """Distinct values of one field, for the agent's sample_field tool.
        Prefers the ValueList (domain values) endpoint; falls back to one
        entities page. Values are untrusted text — truncated."""
        layer_id = mqs_layer_id(layer)
        values = self._value_list(layer_id).get(field)
        if not values:
            values = []
            entities = _extract_entities(self._get_json(self._entities_path(layer_id)))
            for entity in entities:
                properties = entity.get("properties") or entity.get("properties_list")
                source = properties if isinstance(properties, dict) else entity
                value = source.get(field)
                if value is None:
                    continue
                text = str(value)[:_MAX_SAMPLE_CHARS]
                if text not in values:
                    values.append(text)
                if len(values) >= limit:
                    break
        return values[:limit]

    # -- Sync support (beyond the Provider protocol) -------------------------

    def list_remote_layers(self) -> List[dict]:
        """Raw layer dicts from GET /MoriaProject/Layers, for catalog sync."""
        payload = self._get_json("/MoriaProject/Layers")
        layers = _find_entity_list(payload)
        if layers is None:
            raise ProviderError(
                "MQS returned an unrecognized layer-list response from "
                "/MoriaProject/Layers"
            )
        return layers

    # -- helpers -------------------------------------------------------------

    def _value_list(self, layer_id: str) -> Dict[str, List[str]]:
        """Best-effort domain values per field from /MoriaProject/ValueList.
        Accepts {field: [values]} or [{"field"/"name": ..., "values": [...]}].
        Any failure → no samples; the schema/sampling still succeeds."""
        try:
            payload = self._get_json(f"/MoriaProject/ValueList/{layer_id}")
        except ProviderError:
            return {}
        result: Dict[str, List[str]] = {}
        if isinstance(payload, dict) and all(
            isinstance(v, list) for v in payload.values()
        ):
            items = [{"field": k, "values": v} for k, v in payload.items()]
        else:
            items = _extract_entities(payload)
        for item in items:
            name = _first_key(item, ("field", "name", "fieldName", "Field"))
            values = item.get("values") or item.get("Values")
            if not isinstance(name, str) or not isinstance(values, list):
                continue
            result[name] = [str(v)[:_MAX_SAMPLE_CHARS] for v in values if v is not None]
        return result
