"""Cubes provider for time-varying entity locations.

Catalog rows use provider="cubes" and source_url="cubes://db/<dbname>".
The adapter POSTs a one-hour lookback query to /cube/v1/<dbname>, parses
WKT POINT geometry, and preserves every returned JSON field as a feature
property. `eventTime` is the provider-declared temporal field.
"""

from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import quote

import geopandas as gpd
import httpx
from shapely import wkt
from shapely.geometry.base import BaseGeometry

from app.bl.ports import LayerField, LayerMeta, LayerSchema
from app.common.errors import ProviderError
from app.common.geo import WGS84, empty_features_gdf
from app.common.runtime_settings import RuntimeSettingsStore

_TIMEOUT_SECONDS = 30
_RESPONSE_LIST_KEYS = (
    "data", "Data", "results", "Results", "items", "Items",
    "entities", "Entities",
)
_SCHEMA_SAMPLE_LIMIT = 100
_MAX_FIELD_SAMPLES = 5
_MAX_SAMPLE_CHARS = 80
_TIME_FIELD_NAMES = ("eventTime", "arriveTime", "timestamp", "time", "datetime")


def cubes_database_name(layer: LayerMeta) -> str:
    """Extract <dbname> from cubes://db/<dbname>, a bare name, or URL."""
    ignored = {"cube", "v1", "db"}
    segments = [
        part for part in layer.source_url.strip().split("/")
        if part and part.lower() not in ignored
    ]
    if not segments:
        raise ProviderError(
            f"Layer {layer.id} has no Cubes database name in source_url; "
            "expected cubes://db/<dbname>"
        )
    return segments[-1]


def _records(payload: object) -> List[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        if "geometry" in payload:
            return [payload]
        for key in _RESPONSE_LIST_KEYS:
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise ProviderError("Cubes returned an unrecognized response shape")


def _query_body(geometry: Optional[BaseGeometry]) -> dict:
    body = {
        "eventTime": {"TimeBackUnit": "hour", "TimeBackValue": 1},
        "eventTime.not": {"TimeBackUnit": "hour", "TimeBackValue": 1},
        "arriveTime": {"TimeBackUnit": "no_time", "TimeBackValue": 1},
        "arriveTime.not": {"TimeBackUnit": "no_time", "TimeBackValue": 1},
    }
    if geometry is not None:
        body["arriveTime.not"]["Location"] = geometry.wkt
    return body


def _looks_like_iso_datetime(value: object) -> bool:
    if not isinstance(value, str) or "T" not in value:
        return False
    try:
        datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _field_type(name: str, values: List[object]) -> str:
    present = [value for value in values if value is not None]
    if name in _TIME_FIELD_NAMES or any(_looks_like_iso_datetime(v) for v in present):
        return "date"
    if present and all(isinstance(v, bool) for v in present):
        return "boolean"
    if present and all(
        isinstance(v, (int, float)) and not isinstance(v, bool) for v in present
    ):
        return "number"
    return "string"


def _infer_schema(layer_id: str, rows: List[dict]) -> LayerSchema:
    """Infer every non-geometry field from returned JSON; no Cubes schema
    change should require a code change."""
    names: List[str] = []
    for row in rows:
        for raw_name in row:
            name = str(raw_name)
            if name != "geometry" and name not in names:
                names.append(name)
    fields: List[LayerField] = []
    for name in names:
        values = [row.get(name) for row in rows]
        samples: List[str] = []
        for value in values:
            if value is None:
                continue
            sample = str(value)[:_MAX_SAMPLE_CHARS]
            if sample not in samples:
                samples.append(sample)
            if len(samples) >= _MAX_FIELD_SAMPLES:
                break
        fields.append(LayerField(
            name=name, type=_field_type(name, values), samples=samples
        ))
    field_names = {field.name for field in fields}
    temporal_field = next(
        (name for name in _TIME_FIELD_NAMES if name in field_names), None
    )
    if temporal_field is None:
        temporal_field = next(
            (field.name for field in fields if field.type == "date"), None
        )
    return LayerSchema(
        layer_id=layer_id,
        geometry_type="Point",
        fields=fields,
        temporal_field=temporal_field,
    )


class CubesProvider:
    def __init__(
        self,
        settings_store: RuntimeSettingsStore,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self._store = settings_store
        self._transport = transport
        self._schema_cache: Dict[str, LayerSchema] = {}

    def _base_url(self) -> str:
        value = self._store.get().cubes_base_url
        if not value:
            raise ProviderError(
                "Cubes base URL is not configured — set cubes_base_url"
            )
        return value

    def _headers(self) -> Dict[str, str]:
        token = self._store.get().cubes_token
        if not token:
            raise ProviderError(
                "Cubes authorization token is not configured — set cubes_token"
            )
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": token,
        }

    def describe_schema(self, layer: LayerMeta) -> LayerSchema:
        cached = self._schema_cache.get(layer.id)
        if cached is not None:
            return cached
        self.fetch_features(layer, limit=_SCHEMA_SAMPLE_LIMIT)
        return self._schema_cache.get(
            layer.id, _infer_schema(layer.id, [])
        )

    def fetch_features(
        self,
        layer: LayerMeta,
        now: Optional[datetime] = None,
        geometry: Optional[BaseGeometry] = None,
        limit: Optional[int] = None,
    ) -> gpd.GeoDataFrame:
        # `now` belongs to the shared Provider protocol. Cubes evaluates the
        # relative one-hour window server-side, so no client timestamp is sent.
        database = quote(cubes_database_name(layer), safe="")
        path = f"/cube/v1/{database}"
        try:
            with httpx.Client(
                base_url=self._base_url(),
                headers=self._headers(),
                timeout=_TIMEOUT_SECONDS,
                verify=False,
                transport=self._transport,
            ) as client:
                response = client.post(path, json=_query_body(geometry))
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Cubes request failed ({path}): {exc}")
        except ValueError as exc:
            raise ProviderError(f"Cubes returned invalid JSON ({path}): {exc}")

        geometries: List[BaseGeometry] = []
        attributes: List[dict] = []
        rows = _records(payload)
        self._schema_cache[layer.id] = _infer_schema(layer.id, rows)
        if limit is not None:
            rows = rows[:limit]
        for row in rows:
            raw_geometry = row.get("geometry")
            if not isinstance(raw_geometry, str):
                continue
            try:
                parsed = wkt.loads(raw_geometry)
            except Exception:
                continue
            if parsed.geom_type != "Point":
                continue
            geometries.append(parsed)
            attributes.append({key: value for key, value in row.items()
                               if key != "geometry"})
        if not geometries:
            return empty_features_gdf()
        return gpd.GeoDataFrame(attributes, geometry=geometries, crs=WGS84)

    def sample_field_values(
        self, layer: LayerMeta, field: str, limit: int = 20
    ) -> List[str]:
        features = self.fetch_features(layer, limit=max(limit * 5, 20))
        if field not in features.columns:
            return []
        values: List[str] = []
        for value in features[field].dropna():
            text = str(value)[:80]
            if text not in values:
                values.append(text)
            if len(values) >= limit:
                break
        return values
