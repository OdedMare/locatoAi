"""Tyche Our Forces provider.

The upstream API is query-only: every request carries an event-time window and
may carry the caller's WGS84 boundary. Nothing is mirrored or persisted here.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple

import geopandas as gpd
import httpx
from shapely import wkt
from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry

from app.bl.ports.layer_field import LayerField
from app.bl.ports.layer_meta import LayerMeta
from app.bl.ports.layer_schema import LayerSchema
from app.common.errors.provider_error import ProviderError
from app.common.geo import WGS84, empty_features_gdf
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore

_PATH = "/coordinate/v1/ourforces"
_TIMEOUT_SECONDS = 30
_DEFAULT_LOOKBACK = timedelta(hours=1)
_DEFAULT_PAGE_SIZE = 10000
_MAX_FETCHED_ROWS = 100000
_MAX_SAMPLE_CHARS = 80
_SOURCE_URL = "tyche://ourforces"
_LOGGER = logging.getLogger(__name__)

_FIELDS = (
    ("eventTime", "date", "Event occurrence time"),
    ("arriveTime", "date", "Time the event arrived at the repository"),
    ("callSign", "string", "Force call sign"),
    ("forceType", "string", "Force type or reporting platform"),
    ("unit", "string", "Organizational unit"),
    ("netId", "string", "Force/network identifier"),
    ("pstn", "string", "Force telephone number"),
    ("sourceType", "string", "Report source"),
    ("id", "string", "Unique event identifier"),
    ("trigger", "string", "Event type or trigger"),
    ("locationType", "string", "Polygon/location type"),
)


def _service_timestamp(value: datetime) -> str:
    """Render the exact millisecond timestamp format shown in the API docs."""
    normalized = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return normalized.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ProviderError(f"Tyche received an invalid temporal bound: {value}") from exc
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _time_window(
    now: Optional[datetime], temporal_range: Optional[Tuple[str, str]],
) -> Dict[str, str]:
    if temporal_range is not None:
        start, end = (_parse_timestamp(value) for value in temporal_range)
    else:
        end = now or datetime.now(timezone.utc)
        end = end if end.tzinfo is not None else end.replace(tzinfo=timezone.utc)
        start = end - _DEFAULT_LOOKBACK
    if start > end:
        raise ProviderError("Tyche temporal range starts after it ends")
    return {"gte": _service_timestamp(start), "lte": _service_timestamp(end)}


def _location_filter(geometry: BaseGeometry) -> dict:
    """Translate a WGS84 boundary to Tyche's documented object-filter pattern.

    The supplied ReDoc extract documents ``location`` as an object and states
    that polygon values are WKT, but omits its inner schema. Keeping that
    inferred shape in one helper makes an OpenAPI-driven adjustment local.
    """
    return {"match": geometry.wkt}


def _query_body(
    now: Optional[datetime], geometry: Optional[BaseGeometry],
    temporal_range: Optional[Tuple[str, str]], size: int,
    page_tracker: Optional[str] = None,
) -> dict:
    body = {
        "eventTime": {"match": _time_window(now, temporal_range)},
        "size": size,
        "fetchPaging": True,
    }
    if geometry is not None:
        body["location"] = _location_filter(geometry)
    if page_tracker:
        body["pageTracker"] = page_tracker
    return body


def _geometry_from_mapping(value: dict) -> Optional[BaseGeometry]:
    if value.get("type") == "Feature":
        return _parse_geometry(value.get("geometry"))
    if "type" in value and "coordinates" in value:
        try:
            return shape(value)
        except (TypeError, ValueError):
            return None
    for key in ("geometry", "geo", "wkt", "WKT"):
        if key in value:
            return _parse_geometry(value[key])
    lon = value.get("lon", value.get("lng", value.get("longitude")))
    lat = value.get("lat", value.get("latitude"))
    if isinstance(lon, (int, float)) and isinstance(lat, (int, float)):
        return Point(lon, lat)
    return None


def _parse_geometry(value: object) -> Optional[BaseGeometry]:
    if isinstance(value, BaseGeometry):
        return value
    if isinstance(value, dict):
        return _geometry_from_mapping(value)
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        lon, lat = value[0], value[1]
        if isinstance(lon, (int, float)) and isinstance(lat, (int, float)):
            return Point(lon, lat)
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text[0] in "[{":
        try:
            return _parse_geometry(json.loads(text))
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    try:
        return wkt.loads(text)
    except Exception:
        return None


def _rows_to_gdf(rows: List[dict]) -> gpd.GeoDataFrame:
    parsed = [(row, _parse_geometry(row.get("geometry"))) for row in rows]
    valid = [(row, geometry) for row, geometry in parsed
             if geometry is not None and not geometry.is_empty]
    invalid_count = len(rows) - len(valid)
    if invalid_count:
        _LOGGER.warning("Tyche skipped %s rows with invalid geometry", invalid_count)
    if not valid:
        return empty_features_gdf()
    attributes = [
        {key: value for key, value in row.items() if key != "geometry"}
        for row, _ in valid
    ]
    return gpd.GeoDataFrame(
        attributes, geometry=[geometry for _, geometry in valid], crs=WGS84)


def _deduplicate(rows: List[dict]) -> List[dict]:
    unique: Dict[str, dict] = {}
    for row in rows:
        identifier = row.get("id")
        key = (f"id:{identifier}" if identifier is not None else
               json.dumps(row, ensure_ascii=False, sort_keys=True, default=str))
        unique.setdefault(key, row)
    return list(unique.values())


def _validate_source(layer: LayerMeta) -> None:
    if layer.source_url.strip().rstrip("/").lower() != _SOURCE_URL:
        raise ProviderError(
            "Tyche supports only source_url=tyche://ourforces"
        )


class TycheProvider:
    def __init__(
        self,
        settings_store: RuntimeSettingsStore,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self._store = settings_store
        self._transport = transport
        self._samples: Dict[str, List[dict]] = {}

    def describe_schema(self, layer: LayerMeta) -> LayerSchema:
        _validate_source(layer)
        sample_rows = self._samples.get(layer.id, [])
        fields = []
        for name, field_type, description in _FIELDS:
            values = [str(row[name])[:_MAX_SAMPLE_CHARS] for row in sample_rows
                      if row.get(name) is not None]
            fields.append(LayerField(
                name=name, type=field_type, description=description,
                samples=list(dict.fromkeys(values))[:5],
            ))
        known = {field.name for field in fields}
        for name in dict.fromkeys(str(key) for row in sample_rows for key in row
                                  if key != "geometry"):
            if name not in known:
                values = [str(row[name])[:_MAX_SAMPLE_CHARS] for row in sample_rows
                          if row.get(name) is not None]
                fields.append(LayerField(
                    name=name, type="string",
                    samples=list(dict.fromkeys(values))[:5],
                ))
        return LayerSchema(
            layer_id=layer.id,
            geometry_type="Geometry",
            fields=fields,
            source_name="Our Forces",
            source_description="Tyche own-force events and geographic positions",
            temporal_field="eventTime",
        )

    def fetch_features(
        self,
        layer: LayerMeta,
        now: Optional[datetime] = None,
        geometry: Optional[BaseGeometry] = None,
        limit: Optional[int] = None,
        temporal_range: Optional[Tuple[str, str]] = None,
    ) -> gpd.GeoDataFrame:
        _validate_source(layer)
        if limit is not None and limit < 1:
            return empty_features_gdf()
        rows: List[dict] = []
        tracker: Optional[str] = None
        seen_trackers: Set[str] = set()
        with self._client() as client:
            while True:
                remaining = ((limit - len(rows)) if limit is not None
                             else _MAX_FETCHED_ROWS - len(rows))
                if remaining <= 0:
                    break
                size = min(_DEFAULT_PAGE_SIZE, remaining)
                payload = self._post_page(
                    client, _query_body(
                        now, geometry, temporal_range, size, tracker))
                page_rows = payload.get("results")
                if not isinstance(page_rows, list):
                    raise ProviderError("Tyche response must contain a results array")
                rows.extend(item for item in page_rows if isinstance(item, dict))
                rows = _deduplicate(rows)
                has_more = bool(payload.get("hasMoreResults"))
                if not has_more or (limit is not None and len(rows) >= limit):
                    break
                next_tracker = payload.get("pageTracker")
                if not isinstance(next_tracker, str) or not next_tracker:
                    raise ProviderError(
                        "Tyche reported more results without a pageTracker")
                if next_tracker in seen_trackers:
                    raise ProviderError("Tyche returned a repeated pageTracker")
                seen_trackers.add(next_tracker)
                tracker = next_tracker
        if len(rows) >= _MAX_FETCHED_ROWS and limit is None and has_more:
            raise ProviderError(
                f"Tyche returned more than the {_MAX_FETCHED_ROWS} row safety limit; "
                "narrow the time window or map boundary")
        if limit is not None:
            rows = rows[:limit]
        self._samples[layer.id] = rows[:100]
        features = _rows_to_gdf(rows)
        if geometry is not None and not features.empty:
            features = features[features.geometry.intersects(geometry)]
        return features.reset_index(drop=True)

    @staticmethod
    def _post_page(client: httpx.Client, body: dict) -> dict:
        try:
            response = client.post(_PATH, json=body)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Tyche request failed ({_PATH}): {exc}") from exc
        except ValueError as exc:
            raise ProviderError(f"Tyche returned invalid JSON ({_PATH}): {exc}") from exc
        if not isinstance(payload, dict):
            raise ProviderError("Tyche response must be a JSON object")
        return payload

    def sample_field_values(
        self, layer: LayerMeta, field: str, limit: int = 20,
    ) -> List[str]:
        features = self.fetch_features(layer, limit=max(limit * 5, 20))
        if field not in features.columns:
            return []
        values: List[str] = []
        for value in features[field].dropna():
            text = str(value)[:_MAX_SAMPLE_CHARS]
            if text not in values:
                values.append(text)
            if len(values) >= limit:
                break
        return values

    def _base_url(self) -> str:
        value = self._store.get().tyche_base_url
        if not value:
            raise ProviderError(
                "Tyche base URL is not configured — set tyche_base_url")
        return value

    def _client(self) -> httpx.Client:
        username = self._store.get().tyche_username
        if not username:
            raise ProviderError(
                "Tyche username is not configured — set tyche_username")
        token = self._store.get().tyche_token
        if not token:
            raise ProviderError(
                "Tyche authorization token is not configured — set tyche_token")
        return httpx.Client(
            base_url=self._base_url(),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "username": username,
                "Authorization": token,
            },
            timeout=_TIMEOUT_SECONDS,
            verify=self._store.get().tyche_verify_tls,
            transport=self._transport,
        )
