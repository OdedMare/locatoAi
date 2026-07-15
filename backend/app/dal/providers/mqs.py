"""MQS (Moria Query Service) provider: fetches layers over the MQS REST API.

Catalog rows route here with provider='mqs'; their source_url stores the
MQS layer id as "mqs://layer/{layerId}" (base-URL-independent — the live
base URL is the mqs_base_url runtime setting, read on every call). The
last path segment is the layer id, so a bare id or a pasted full URL
(including a pasted layer_entities_link) also work.

The paginated Entities response carries the fixed transport fields below.
The single-entity endpoint additionally carries `property_list`, which is
the authoritative source for searchable business attributes such as name,
description, essence and type:

    exclusive_id: {data_store_name, layer_id, entity_id, history_id}
    classification: {triangle, clearence_level (sic — preserve the
                     service's misspelling), source_id}
    date: "DD/MM/YYYY HH:MM:SS"
    link: direct URL to the single-entity resource
    geo: {wkt: "POLYGON ((lon lat alt, ...))", area, perimeter}

`property_list` is flattened into ordinary GeoDataFrame columns using its
original field names. Consequently the same attributes are available to
metadata/tag generation, schema/value sampling, attribute filters and every
spatial operation that carries the input feature rows forward.

GET /MoriaProject/{layer_id}/Entities requires the `User_ID` header (the
mqs_user_id runtime setting) and `Accept: application/json`, and is
genuinely paginated: `from`/`to` query params (defaults 0/10000), and the
response is `{"next_page": <url-or-null>, "total_entities": N,
"entities_list": [...]}`. fetch_features follows next_page until it is
absent, guarded by _MAX_FEATURES. (The doc's very first section showed a
bare-array response with no wrapper — _extract_entities stays lenient and
accepts both.)

GET /MoriaProject/{layer_id}/Entities/{entity_id} returns the entity detail.
The provider follows it for every fetched list entity unless that entity
already embeds `property_list`.

WKT coordinates are lon/lat (the doc says to confirm the CRS with the
service owner); assumed WGS84 — if a real instance serves ITM
(EPSG:2039), fix it inside _ensure_wgs84.

Spatial pushdown: the same /Entities route also accepts POST with a
{"filter": {"complex_operators": {...}}} body (per a follow-up doc
excerpt covering geo_bounding_box/geo_polygon/geo_distance — the
simple_operators section, e.g. ids/match/IN, was not provided and is not
implemented). fetch_features/sample_field_values take an optional
`geometry` (always WGS84); when given, a rectangular geometry becomes
geo_bounding_box and anything else becomes geo_polygon (WKT), and the
request is POSTed instead of GET'd — same pagination params, same
response envelope assumed (not separately confirmed for POST, since no
different shape was documented). This is always an optimization: it
narrows what MQS returns, but callers (within_geometry) still re-filter
client-side, so an instance that ignores the filter body stays correct,
just slower.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, quote, urlparse

import geopandas as gpd
import httpx
from shapely import wkt
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry

from app.bl.ports.layer_field import LayerField
from app.bl.ports.layer_meta import LayerMeta
from app.bl.ports.layer_schema import LayerSchema
from app.common.errors.provider_error import ProviderError
from app.common.geo import WGS84, empty_features_gdf
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 30
_MAX_FEATURES = 50000
_PAGE_SIZE = 10000  # matches the doc's default `to` value

# Same truncation policy as the mock provider: sample values are untrusted
# text that ends up in LLM prompts.
_MAX_SAMPLE_CHARS = 40

_ENTITY_LIST_KEYS = (
    "entities_list", "EntitiesList", "features", "Features", "entities",
    "Entities", "data", "Data", "results", "Results", "items", "Items",
)
_LAYER_LIST_KEYS = ("layers_list", "LayersList", "layers", "Layers")
_ENTITY_ID_KEYS = ("id", "entityId", "entity_id", "Id")
_PROPERTY_LIST_KEYS = (
    "property_list", "propertyList", "PropertyList", "Property_List",
    "properties", "Properties",
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

# Fixed transport fields present alongside dynamic property_list attributes.
# `clearence_level` is the service's own (misspelled) name; preserve it.
_FIXED_FIELDS = (
    LayerField(name="triangle", type="string", description="קוד מיון (Triangle classification code)", metadata_relevant=False),
    LayerField(name="clearence_level", type="string", description="רמת הסיווג/הרשאה (Clearance level)", metadata_relevant=False),
    LayerField(name="source_id", type="number", description="מזהה מערכת המקור (Source system id)", metadata_relevant=False),
    LayerField(name="date", type="date", description="תאריך ושעת הרשומה (Record date)", metadata_relevant=False),
    LayerField(name="area", type="number", description="שטח הפוליגון (Polygon area)", metadata_relevant=False),
    LayerField(name="perimeter", type="number", description="היקף הפוליגון (Polygon perimeter)", metadata_relevant=False),
)
_TEMPORAL_FIELD = "date"  # the only date-typed field that exists


def _temporal_field_override(layer: LayerMeta) -> Tuple[bool, Optional[str]]:
    """(has_override, field_name_or_None) from the layer's tags. A
    "no_temporal_field" tag opts a layer out; "temporal_field:<name>"
    forces a specific field. has_override=False means "use _TEMPORAL_FIELD"."""
    for tag in layer.tags:
        if tag == "no_temporal_field":
            return True, None
        if tag.startswith("temporal_field:"):
            return True, tag[len("temporal_field:"):].strip() or None
    return False, None


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


def _find_list(payload: object, keys: Tuple[str, ...]) -> Optional[List[dict]]:
    """Find a list of dicts in common MQS/ASP.NET response envelopes, or a
    bare array. Returning None (rather than []) lets callers distinguish
    an unrecognized shape from a genuinely empty result."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in keys:
            if key not in payload:
                continue
            value = payload[key]
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return None


def _parse_geometry(value: object) -> Optional[BaseGeometry]:
    try:
        if isinstance(value, dict):
            nested_wkt = value.get("wkt") or value.get("WKT")
            if isinstance(nested_wkt, str) and nested_wkt.strip():
                return wkt.loads(nested_wkt)
        if isinstance(value, str) and value.strip():
            return wkt.loads(value)
    except Exception:
        return None
    return None


def _entity_id(entity: dict) -> Optional[str]:
    """Return the stable MQS entity id from either the fixed envelope or a
    common top-level spelling."""
    exclusive_id = entity.get("exclusive_id")
    value = (
        _first_key(exclusive_id, _ENTITY_ID_KEYS)
        if isinstance(exclusive_id, dict)
        else _first_key(entity, _ENTITY_ID_KEYS)
    )
    return str(value) if value is not None else None


def _property_value(value: object) -> object:
    """Unwrap a common {value: ...} wrapper while keeping scalar values."""
    if isinstance(value, dict):
        nested = _first_key(value, _PROPERTY_VALUE_KEYS)
        if nested is not None:
            return nested
    return value


def _property_attributes(entity: dict) -> Dict[str, object]:
    """Normalize MQS property_list variants into flat searchable columns.

    Deployments have returned both a JSON object and a list of name/value
    objects. Unknown nested values are stringified by GeoPandas at response
    serialization time; geometry is never read from property_list.
    """
    raw = _first_key(entity, _PROPERTY_LIST_KEYS)
    attributes: Dict[str, object] = {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return attributes
    if isinstance(raw, dict):
        nested = _first_key(raw, _PROPERTY_LIST_KEYS)
        if isinstance(nested, (dict, list)):
            return _property_attributes({"property_list": nested})
        for key, value in raw.items():
            name = str(key).strip()
            if name and name != "geometry":
                attributes[name] = _property_value(value)
        return attributes
    if not isinstance(raw, list):
        return attributes
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = _first_key(item, _PROPERTY_NAME_KEYS)
        value = _first_key(item, _PROPERTY_VALUE_KEYS)
        if name is None and len(item) == 1:
            name, value = next(iter(item.items()))
        field_name = str(name).strip() if name is not None else ""
        if field_name and field_name != "geometry":
            attributes[field_name] = _property_value(value)
    return attributes


def _entity_to_record(entity: dict) -> Optional[Tuple[BaseGeometry, dict]]:
    """One MQS entity → (geometry, attributes), or None if no usable
    geometry. Fixed transport fields and dynamic property_list fields are
    flattened into the same attribute row."""
    geometry = _parse_geometry(entity.get("geo"))
    if geometry is None:
        return None

    attributes: dict = {}
    entity_id = _entity_id(entity)
    if entity_id is not None:
        attributes["id"] = entity_id

    classification = entity.get("classification")
    if isinstance(classification, dict):
        for key in ("triangle", "clearence_level", "source_id"):
            if key in classification:
                attributes[key] = classification[key]

    if "date" in entity:
        attributes["date"] = entity["date"]
    if "link" in entity:
        attributes["link"] = entity["link"]

    geo = entity.get("geo")
    if isinstance(geo, dict):
        for key in ("area", "perimeter"):
            if key in geo:
                attributes[key] = geo[key]

    # Business properties deliberately remain top-level, under the original
    # MQS names, so the planner can emit filters such as field="שם".
    for key, value in _property_attributes(entity).items():
        if key not in attributes:  # preserve stable transport identifiers
            attributes[key] = value

    return geometry, attributes


# A loose WGS84 lon/lat sanity envelope (world bounds, not just Israel —
# this is a smoke check, not a real CRS validation). ITM (EPSG:2039)
# easting/northing values are 6-7 digit numbers and fall way outside it,
# so mixing up the two CRSs is caught immediately instead of silently
# producing wrong/empty spatial results downstream (within_geometry,
# near, directional all assume WGS84 degrees).
_WGS84_LON_RANGE = (-180.0, 180.0)
_WGS84_LAT_RANGE = (-90.0, 90.0)


def _looks_like_wgs84(gdf: gpd.GeoDataFrame) -> bool:
    bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
    if len(bounds) != 4 or any(b != b for b in bounds):  # nan → empty/no geometry
        return True
    minx, miny, maxx, maxy = bounds
    return (
        _WGS84_LON_RANGE[0] <= minx <= maxx <= _WGS84_LON_RANGE[1]
        and _WGS84_LAT_RANGE[0] <= miny <= maxy <= _WGS84_LAT_RANGE[1]
    )


def _geometry_filter_body(geometry: BaseGeometry) -> dict:
    """A WGS84 geometry → the {"filter": {"complex_operators": {...}}}
    body for MQS's POST spatial filter. A geometry equal to its own
    bounding box (an axis-aligned rectangle — the common viewport case)
    uses geo_bounding_box; anything else (drawn polygons) uses geo_polygon
    with WKT, per the doc excerpt covering both operators."""
    minx, miny, maxx, maxy = geometry.bounds
    if geometry.equals(box(minx, miny, maxx, maxy)):
        return {
            "filter": {
                "complex_operators": {
                    "geo_bounding_box": {
                        "geo": {
                            "type": "AND",
                            "values": [{
                                "location_top_left": {"lat": maxy, "lon": minx},
                                "location_bottom_right": {"lat": miny, "lon": maxx},
                            }],
                        }
                    }
                }
            }
        }
    return {
        "filter": {
            "complex_operators": {
                "geo_polygon": {
                    "geo": {"type": "IN", "values": [geometry.wkt]}
                }
            }
        }
    }


def _ensure_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """MQS WKT is assumed WGS84 lon/lat (per the doc's note to confirm the
    SRID with the service owner). If a live instance turns out to serve
    ITM, change this to set_crs(ISRAEL_TM).to_crs(WGS84) — the coordinate
    sanity check below turns that mismatch into a loud error instead of
    silently wrong spatial results."""
    if gdf.crs is None:
        gdf = gdf.set_crs(WGS84)
    if not _looks_like_wgs84(gdf):
        bounds = gdf.total_bounds
        raise ProviderError(
            f"MQS geometry coordinates {list(bounds)} are outside WGS84 "
            "lon/lat range — the service may be serving a projected CRS "
            "(e.g. ITM/EPSG:2039); fix _ensure_wgs84 in mqs.py"
        )
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

    # -- Provider protocol ---------------------------------------------------

    def describe_schema(self, layer: LayerMeta) -> LayerSchema:
        # There is no layer field-list endpoint. Infer business fields and
        # bounded samples from entity details, then append them to fixed fields.
        has_override, temporal_field = _temporal_field_override(layer)
        if not has_override:
            temporal_field = _TEMPORAL_FIELD
        dynamic: Dict[str, LayerField] = {}
        layer_id = mqs_layer_id(layer)
        with self._client() as client:
            for entity in self._iter_all_entities(client, layer_id, limit=20):
                detail = self._entity_detail(client, layer_id, entity)
                for name, value in _property_attributes(detail).items():
                    sample = str(value)[:_MAX_SAMPLE_CHARS]
                    existing = dynamic.get(name)
                    if existing is None:
                        field_type = (
                            "number" if isinstance(value, (int, float))
                            and not isinstance(value, bool) else "string"
                        )
                        dynamic[name] = LayerField(
                            name=name, type=field_type, samples=[sample]
                        )
                    elif sample not in existing.samples and len(existing.samples) < 5:
                        existing.samples.append(sample)
        logger.info(
            "MQS schema layer=%s dynamic_fields=%d names=%s",
            layer_id, len(dynamic), list(dynamic),
        )
        return LayerSchema(
            layer_id=layer.id,
            geometry_type="Polygon",
            fields=list(_FIXED_FIELDS) + list(dynamic.values()),
            temporal_field=temporal_field,
        )

    def fetch_features(
        self,
        layer: LayerMeta,
        now: Optional[datetime] = None,
        geometry: Optional[BaseGeometry] = None,
        limit: Optional[int] = None,
    ) -> gpd.GeoDataFrame:
        # `now` is part of the Provider protocol (mock temporal synthesis);
        # MQS serves real data, so it is ignored. `geometry`, when given,
        # is pushed down as a POST filter (see module docstring) — an
        # optimization only; nothing downstream depends on MQS honoring it.
        # `limit` caps pagination to a small first page (e.g. metadata
        # sampling) instead of fetching the whole layer.
        layer_id = mqs_layer_id(layer)
        geometries: List[BaseGeometry] = []
        attribute_rows: List[dict] = []
        skipped = 0
        with self._client() as client:
            for entity in self._iter_all_entities(client, layer_id, geometry, limit):
                detail = self._entity_detail(client, layer_id, entity)
                record = _entity_to_record(detail)
                if record is None:
                    skipped += 1
                    continue
                geometries.append(record[0])
                attribute_rows.append(record[1])
        if skipped:
            logger.warning(
                "MQS layer %s: skipped %d entities without parseable "
                "geometry", layer_id, skipped,
            )
        if not geometries:
            return empty_features_gdf()
        gdf = gpd.GeoDataFrame(attribute_rows, geometry=geometries, crs=WGS84)
        return _ensure_wgs84(gdf)

    def sample_field_values(
        self, layer: LayerMeta, field: str, limit: int = 20
    ) -> List[str]:
        """Distinct fixed or property_list values sampled from entity details.
        Values are untrusted text — truncated."""
        layer_id = mqs_layer_id(layer)
        values: List[str] = []
        sample_size = min(_PAGE_SIZE, max(limit * 5, 20))
        with self._client() as client:
            entities, _ = self._entities_page(
                client, layer_id, {"from": 0, "to": sample_size}
            )
            for entity in entities:
                detail = self._entity_detail(client, layer_id, entity)
                record = _entity_to_record(detail)
                if record is None:
                    continue
                value = record[1].get(field)
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
        with self._client() as client:
            payload = self._get_json(client, "/MoriaProject/Layers")
        layers = _find_list(payload, _LAYER_LIST_KEYS)
        if layers is None:
            raise ProviderError(
                "MQS returned an unrecognized layer-list response from "
                "/MoriaProject/Layers"
            )
        return layers

    # -- HTTP plumbing (private) ---------------------------------------------

    def _base_url(self) -> str:
        base_url = self._store.get().mqs_base_url
        if not base_url:
            raise ProviderError(
                "MQS base URL is not configured — set mqs_base_url in the "
                "settings panel"
            )
        return base_url

    def _headers(self) -> Dict[str, str]:
        # Both required per the doc. User_ID is deployment-specific (the
        # doc's example is "tt/T"), so it comes from the mqs_user_id
        # runtime setting; when unset, no header is sent and an instance
        # that enforces it will reject the request (surfaces as ProviderError).
        headers = {"Accept": "application/json"}
        user_id = self._store.get().mqs_user_id
        if user_id:
            headers["User_ID"] = user_id
        return headers

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self._base_url(),
            timeout=_TIMEOUT_SECONDS,
            verify=self._store.get().mqs_verify_tls,
            transport=self._transport,
            headers=self._headers(),
        )

    def _get_json(
        self, client: httpx.Client, path: str, params: Optional[dict] = None
    ) -> object:
        try:
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

    def _post_json(
        self, client: httpx.Client, path: str, body: dict, params: Optional[dict] = None
    ) -> object:
        try:
            response = client.post(path, json=body, params=params)
            logger.info("MQS POST %s -> %s", response.request.url,
                        response.status_code)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"MQS request failed ({path}): {exc}")
        except ValueError as exc:
            raise ProviderError(f"MQS returned invalid JSON ({path}): {exc}")

    def _entities_page(
        self,
        client: httpx.Client,
        layer_id: str,
        params: Optional[dict],
        geometry: Optional[BaseGeometry] = None,
    ) -> Tuple[List[dict], Optional[str]]:
        """One page of entities_list + the next_page URL, or (entities, None)
        for a doc-variant response with no pagination wrapper at all.

        geometry, when given, switches the request from GET to POST with a
        geo_bounding_box/geo_polygon filter body (spatial pushdown — an
        optimization only, see module docstring); pagination params are
        still applied the same way on both paths.
        """
        path = f"/MoriaProject/{layer_id}/Entities"
        if geometry is not None:
            payload = self._post_json(
                client, path, _geometry_filter_body(geometry), params
            )
        else:
            payload = self._get_json(client, path, params)
        entities = _find_list(payload, _ENTITY_LIST_KEYS)
        if entities is None:
            raise ProviderError(
                f"MQS layer {layer_id} returned an unrecognized Entities "
                "response shape"
            )
        next_page = payload.get("next_page") if isinstance(payload, dict) else None
        return entities, (next_page if isinstance(next_page, str) and next_page else None)

    @staticmethod
    def _next_page_params(next_page_url: str) -> dict:
        """next_page is a full URL; only its from/to query params are
        reused (the base URL/path are already fixed by this client)."""
        query = parse_qs(urlparse(next_page_url).query)
        return {key: values[0] for key, values in query.items() if values}

    def _iter_all_entities(
        self,
        client: httpx.Client,
        layer_id: str,
        geometry: Optional[BaseGeometry] = None,
        limit: Optional[int] = None,
    ):
        # limit caps the *first page size* rather than truncating after a
        # full fetch — a metadata/tagging sample (limit=100) must cost one
        # small request, not a full paginated fetch of the whole layer.
        page_size = min(_PAGE_SIZE, limit) if limit is not None else _PAGE_SIZE
        params = {"from": 0, "to": page_size}
        fetched = 0
        while True:
            entities, next_page = self._entities_page(client, layer_id, params, geometry)
            fetched += len(entities)
            if limit is not None and fetched >= limit:
                for entity in entities[: limit - (fetched - len(entities))]:
                    yield entity
                return
            if fetched > _MAX_FEATURES:
                raise ProviderError(
                    f"MQS layer {layer_id} returned more than the "
                    f"{_MAX_FEATURES} feature limit — narrow the layer or "
                    "raise the cap"
                )
            for entity in entities:
                yield entity
            if next_page is None:
                return
            params = self._next_page_params(next_page)

    def _entity_detail(
        self, client: httpx.Client, layer_id: str, entity: dict
    ) -> dict:
        """Return an entity enriched with detail-only property_list fields."""
        if _first_key(entity, _PROPERTY_LIST_KEYS) is not None:
            return entity
        entity_id = _entity_id(entity)
        if entity_id is None:
            logger.warning("MQS layer %s: entity has no entity_id", layer_id)
            return entity
        path = f"/MoriaProject/{layer_id}/Entities/{quote(entity_id, safe='')}"
        payload = self._get_json(client, path)
        detail = payload
        if isinstance(payload, dict):
            # Accept wrappers such as {"entity": {...}} as well as a bare object.
            for key in ("entity", "Entity", "data", "Data"):
                if isinstance(payload.get(key), dict):
                    detail = payload[key]
                    break
        if not isinstance(detail, dict):
            logger.warning(
                "MQS entity %s returned an unrecognized detail shape; "
                "using list-entity fields only", entity_id,
            )
            return entity
        merged = dict(entity)
        merged.update(detail)
        return merged
