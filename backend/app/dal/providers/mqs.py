"""MQS (Moria Query Service) provider: fetches layers over the MQS REST API.

Catalog rows route here with provider='mqs'; their source_url stores the
MQS layer id as "mqs://layer/{layerId}" (base-URL-independent — the live
base URL is the mqs_base_url runtime setting, read on every call). The
last path segment is the layer id, so a bare id or a pasted full URL
(including a pasted layer_entities_link) also work.

Per the real MoriaProject API doc (both the original Entities doc and the
"Additional API Endpoints and Pagination" update), an entity has NO
free-form per-layer attribute table — every entity, in the list response
or the single-entity response, carries exactly the same fixed shape:

    exclusive_id: {data_store_name, layer_id, entity_id, history_id}
    classification: {triangle, clearence_level (sic — preserve the
                     service's misspelling), source_id}
    date: "DD/MM/YYYY HH:MM:SS"
    link: direct URL to the single-entity resource
    geo: {wkt: "POLYGON ((lon lat alt, ...))", area, perimeter}

So describe_schema/sample_field_values expose exactly these fixed fields
(_FIXED_FIELDS below) — there is no Layers/{id} field-list endpoint or
ValueList endpoint in this API; earlier code that guessed at one has been
removed.

GET /MoriaProject/{layer_id}/Entities requires the `User_ID` header (the
mqs_user_id runtime setting) and `Accept: application/json`, and is
genuinely paginated: `from`/`to` query params (defaults 0/10000), and the
response is `{"next_page": <url-or-null>, "total_entities": N,
"entities_list": [...]}`. fetch_features follows next_page until it is
absent, guarded by _MAX_FEATURES. (The doc's very first section showed a
bare-array response with no wrapper — _extract_entities stays lenient and
accepts both.)

GET /MoriaProject/{layer_id}/Entities/{entity_id} returns a single entity
(same shape as one entities_list item) — not currently used by this
provider (fetch-all-filter-locally makes it unnecessary) but kept in mind
for a future per-entity refresh path.

WKT coordinates are lon/lat (the doc says to confirm the CRS with the
service owner); assumed WGS84 — if a real instance serves ITM
(EPSG:2039), fix it inside _ensure_wgs84.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import geopandas as gpd
import httpx
from shapely import wkt
from shapely.geometry.base import BaseGeometry

from app.bl.ports import LayerField, LayerMeta, LayerSchema
from app.common.errors import ProviderError
from app.common.geo import WGS84, empty_features_gdf
from app.common.runtime_settings import RuntimeSettingsStore

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

# The only fields an entity actually has, per the real API doc — no
# per-layer attribute schema exists. `clearence_level` is the service's
# own (misspelled) name; preserved verbatim rather than "corrected".
_FIXED_FIELDS = (
    LayerField(name="triangle", type="string", description="קוד מיון (Triangle classification code)"),
    LayerField(name="clearence_level", type="string", description="רמת הסיווג/הרשאה (Clearance level)"),
    LayerField(name="source_id", type="number", description="מזהה מערכת המקור (Source system id)"),
    LayerField(name="date", type="date", description="תאריך ושעת הרשומה (Record date)"),
    LayerField(name="area", type="number", description="שטח הפוליגון (Polygon area)"),
    LayerField(name="perimeter", type="number", description="היקף הפוליגון (Polygon perimeter)"),
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


def _entity_to_record(entity: dict) -> Optional[Tuple[BaseGeometry, dict]]:
    """One MQS entity → (geometry, attributes), or None if no usable
    geometry. Only the doc's fixed shape is supported — see module
    docstring for the field list."""
    geometry = _parse_geometry(entity.get("geo"))
    if geometry is None:
        return None

    attributes: dict = {}
    exclusive_id = entity.get("exclusive_id")
    if isinstance(exclusive_id, dict):
        entity_id = _first_key(exclusive_id, _ENTITY_ID_KEYS)
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

    return geometry, attributes


def _ensure_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """MQS WKT is assumed WGS84 lon/lat (per the doc's note to confirm the
    SRID with the service owner). If a live instance turns out to serve
    ITM, change this to set_crs(ISRAEL_TM).to_crs(WGS84)."""
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

    def _entities_page(
        self, client: httpx.Client, layer_id: str, params: Optional[dict]
    ) -> Tuple[List[dict], Optional[str]]:
        """One page of entities_list + the next_page URL, or (entities, None)
        for a doc-variant response with no pagination wrapper at all."""
        payload = self._get_json(
            client, f"/MoriaProject/{layer_id}/Entities", params
        )
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

    def _iter_all_entities(self, client: httpx.Client, layer_id: str):
        params = {"from": 0, "to": _PAGE_SIZE}
        fetched = 0
        while True:
            entities, next_page = self._entities_page(client, layer_id, params)
            fetched += len(entities)
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

    # -- Provider protocol ---------------------------------------------------

    def describe_schema(self, layer: LayerMeta) -> LayerSchema:
        # No per-layer field-list endpoint exists in this API — every
        # entity has exactly _FIXED_FIELDS (see module docstring).
        has_override, temporal_field = _temporal_field_override(layer)
        if not has_override:
            temporal_field = _TEMPORAL_FIELD
        return LayerSchema(
            layer_id=layer.id,
            geometry_type="Polygon",
            fields=list(_FIXED_FIELDS),
            temporal_field=temporal_field,
        )

    def fetch_features(
        self, layer: LayerMeta, now: Optional[datetime] = None
    ) -> gpd.GeoDataFrame:
        # `now` is part of the Provider protocol (mock temporal synthesis);
        # MQS serves real data, so it is ignored.
        layer_id = mqs_layer_id(layer)
        geometries: List[BaseGeometry] = []
        attribute_rows: List[dict] = []
        skipped = 0
        with self._client() as client:
            for entity in self._iter_all_entities(client, layer_id):
                record = _entity_to_record(entity)
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
        """Distinct values of one of _FIXED_FIELDS, sampled from a page of
        entities (no dedicated domain-values endpoint exists in this API).
        Values are untrusted text — truncated."""
        if field not in {f.name for f in _FIXED_FIELDS}:
            return []
        layer_id = mqs_layer_id(layer)
        values: List[str] = []
        with self._client() as client:
            entities, _ = self._entities_page(
                client, layer_id, {"from": 0, "to": _PAGE_SIZE}
            )
        for entity in entities:
            record = _entity_to_record(entity)
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
