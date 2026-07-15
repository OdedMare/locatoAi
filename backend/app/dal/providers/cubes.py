"""Cubes provider for metadata and time-varying entity locations."""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import quote

import geopandas as gpd
import httpx
from shapely import wkt
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry

from app.bl.ports.layer_field import LayerField
from app.bl.ports.layer_meta import LayerMeta
from app.bl.ports.layer_parameter import LayerParameter
from app.bl.ports.layer_schema import LayerSchema
from app.common.errors.provider_error import ProviderError
from app.common.geo import WGS84, empty_features_gdf
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore

_TIMEOUT_SECONDS = 30
_RESPONSE_LIST_KEYS = (
    "data", "Data", "results", "Results", "items", "Items",
    "entities", "Entities",
)
_SCHEMA_SAMPLE_LIMIT = 100
_MAX_FIELD_SAMPLES = 5
_MAX_SAMPLE_CHARS = 80
_TIME_FIELD_NAMES = ("eventTime", "arriveTime", "timestamp", "time", "datetime")
_PARAMETER_OPERATORS = ("match", "not")
_DEFAULT_PARAMETER_KEYS = (
    "eventTime", "eventTime.not", "arriveTime", "arriveTime.not",
)
_DEFAULT_RESULTS_LIMIT = 10000
_MAX_CHUNK_DEPTH = 5
_MAX_FETCHED_ROWS = 100000
logger = logging.getLogger(__name__)


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


def _parameter_parts(name: str) -> Tuple[str, Optional[str]]:
    base, separator, operator = name.rpartition(".")
    if separator and operator.lower() in _PARAMETER_OPERATORS:
        return base, operator.lower()
    return name, None


def _parameter_key(base: str, operator: Optional[str]) -> str:
    return base if operator is None else f"{base}.{operator}"


def _declared_parameter_keys(parameters: List[LayerParameter]) -> List[str]:
    keys: List[str] = []
    for parameter in parameters or []:
        base, operator = _parameter_parts(parameter.name)
        declared = (operator,) if operator else (None, "not")
        for item in declared:
            key = _parameter_key(base, item)
            if key not in keys:
                keys.append(key)
    return keys


def _iso_milliseconds(value: datetime) -> str:
    normalized = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return normalized.astimezone(timezone.utc).isoformat(
        timespec="milliseconds").replace("+00:00", "Z")


def _absolute_window(now: Optional[datetime], temporal_range):
    if temporal_range is not None:
        return {"From": temporal_range[0], "To": temporal_range[1]}
    end = now or datetime.now(timezone.utc)
    return {"From": _iso_milliseconds(end - timedelta(hours=1)),
            "To": _iso_milliseconds(end)}


def _parameter_value(key: str, now: Optional[datetime], temporal_range) -> dict:
    base, operator = _parameter_parts(key)
    if operator == "match":
        return _absolute_window(now, temporal_range)
    unit = "no_time" if base == "arriveTime" and operator is None else "hour"
    return {"TimeBackValue": "1", "TimeBackUnit": unit}


def _location_key(body: dict) -> Optional[str]:
    for key in ("arriveTime.not", "eventTime.not"):
        if key in body:
            return key
    return next((key for key in body if _parameter_parts(key)[0] in _TIME_FIELD_NAMES),
                None)


def _query_body(
    geometry: Optional[BaseGeometry], parameters: Optional[List[LayerParameter]] = None,
    now: Optional[datetime] = None, temporal_range=None,
) -> dict:
    keys = (_declared_parameter_keys(parameters) if parameters
            else list(_DEFAULT_PARAMETER_KEYS))
    body = {key: _parameter_value(key, now, temporal_range) for key in keys
            if _parameter_parts(key)[0] in _TIME_FIELD_NAMES}
    _validate_required_parameters(parameters or [], body)
    location_key = _location_key(body)
    if geometry is not None and location_key is not None:
        body[location_key]["Location"] = geometry.wkt
    return body


def _validate_required_parameters(parameters: List[LayerParameter], body: dict) -> None:
    for parameter in parameters:
        base, operator = _parameter_parts(parameter.name)
        key = _parameter_key(base, operator)
        if parameter.required and key not in body:
            raise ProviderError(
                f"Cubes parameter '{parameter.name}' is required and has no configured value"
            )


def _results_limit(metadata: dict) -> int:
    value = metadata.get("ResultsLimit")
    return value if isinstance(value, int) and value > 0 else _DEFAULT_RESULTS_LIMIT


def _spatial_chunks(geometry: BaseGeometry) -> List[BaseGeometry]:
    min_x, min_y, max_x, max_y = geometry.bounds
    middle_x = (min_x + max_x) / 2
    middle_y = (min_y + max_y) / 2
    tiles = (
        box(min_x, min_y, middle_x, middle_y),
        box(middle_x, min_y, max_x, middle_y),
        box(min_x, middle_y, middle_x, max_y),
        box(middle_x, middle_y, max_x, max_y),
    )
    return [part for tile in tiles
            for part in [geometry.intersection(tile)]
            if not part.is_empty and part.area > 0]


def _deduplicate_rows(rows: List[dict]) -> List[dict]:
    unique: Dict[str, dict] = {}
    for row in rows:
        key = json.dumps(row, sort_keys=True, ensure_ascii=False, default=str)
        unique.setdefault(key, row)
    return list(unique.values())


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


def _field_names(rows: List[dict]) -> List[str]:
    names: List[str] = []
    for row in rows:
        for raw_name in row:
            name = str(raw_name)
            if name != "geometry" and name not in names:
                names.append(name)
    return names


def _samples(values: List[object]) -> List[str]:
    present = [str(value)[:_MAX_SAMPLE_CHARS]
               for value in values if value is not None]
    return list(dict.fromkeys(present))[:_MAX_FIELD_SAMPLES]


def _inferred_field(name: str, rows: List[dict]) -> LayerField:
    values = [row.get(name) for row in rows]
    return LayerField(name=name, type=_field_type(name, values),
                      samples=_samples(values))


def _infer_schema(layer_id: str, rows: List[dict]) -> LayerSchema:
    fields = [_inferred_field(name, rows) for name in _field_names(rows)]
    field_names = {field.name for field in fields}
    temporal = next((name for name in _TIME_FIELD_NAMES if name in field_names), None)
    temporal = temporal or next((field.name for field in fields
                                 if field.type == "date"), None)
    return LayerSchema(layer_id=layer_id, geometry_type="Point", fields=fields,
                       temporal_field=temporal)


def _parse_point(row: dict) -> Optional[BaseGeometry]:
    raw = row.get("geometry")
    if not isinstance(raw, str):
        return None
    try:
        geometry = wkt.loads(raw)
        return geometry if geometry.geom_type == "Point" else None
    except Exception:
        return None


def _rows_to_gdf(rows: List[dict]) -> gpd.GeoDataFrame:
    parsed = [(row, _parse_point(row)) for row in rows]
    parsed = [(row, geometry) for row, geometry in parsed if geometry is not None]
    if not parsed:
        return empty_features_gdf()
    attributes = [{key: value for key, value in row.items() if key != "geometry"}
                  for row, _ in parsed]
    return gpd.GeoDataFrame(attributes, geometry=[item[1] for item in parsed], crs=WGS84)


def _metadata_fields(payload: dict) -> List[LayerField]:
    fields = []
    for item in payload.get("Fields") or []:
        if not isinstance(item, dict) or not item.get("Name"):
            continue
        description = str(item.get("DisplayName") or "")
        details = str(item.get("Description") or "")
        fields.append(LayerField(
            name=str(item["Name"]), type=str(item.get("Type") or "string").lower(),
            description=" — ".join(value for value in (description, details) if value),
        ))
    return fields


def _metadata_parameters(payload: dict) -> List[LayerParameter]:
    parameters = []
    for item in payload.get("Parameters") or []:
        if not isinstance(item, dict) or not item.get("Name"):
            continue
        options = [str(option.get("Value")) for option in item.get("Options") or []
                   if isinstance(option, dict) and option.get("Value") is not None]
        parameters.append(LayerParameter(
            name=str(item["Name"]), type=str(item.get("Type") or "string").lower(),
            display_name=str(item.get("DisplayName") or ""),
            description=str(item.get("Description") or ""),
            required=bool(item.get("IsRequired")),
            single_value=bool(item.get("IsSingleValue", True)), options=options,
        ))
    return parameters


def _merge_schema(layer_id: str, metadata: dict,
                  sampled: Optional[LayerSchema]) -> LayerSchema:
    declared = _metadata_fields(metadata)
    samples = {field.name: field for field in (sampled.fields if sampled else [])}
    merged = []
    for field in declared:
        sample = samples.pop(field.name, None)
        if sample is not None:
            field.samples = sample.samples
        merged.append(field)
    merged.extend(samples.values())
    names = {field.name for field in merged}
    temporal = next((name for name in _TIME_FIELD_NAMES if name in names), None)
    return LayerSchema(layer_id=layer_id, geometry_type="Point", fields=merged,
                       parameters=_metadata_parameters(metadata),
                       source_name=str(metadata.get("Name") or ""),
                       source_description=str(metadata.get("Description") or ""),
                       temporal_field=temporal or (sampled.temporal_field if sampled else None))


class CubesProvider:
    def __init__(
        self,
        settings_store: RuntimeSettingsStore,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self._store = settings_store
        self._transport = transport
        self._schema_cache: Dict[str, LayerSchema] = {}
        self._metadata_cache: Dict[str, dict] = {}

    def describe_schema(self, layer: LayerMeta) -> LayerSchema:
        metadata = self._get_metadata(layer)
        sampled = self._schema_cache.get(layer.id)
        if sampled is None:
            self.fetch_features(layer, limit=_SCHEMA_SAMPLE_LIMIT)
            sampled = self._schema_cache.get(layer.id)
        return _merge_schema(layer.id, metadata, sampled)

    def fetch_features(
        self,
        layer: LayerMeta,
        now: Optional[datetime] = None,
        geometry: Optional[BaseGeometry] = None,
        limit: Optional[int] = None,
        temporal_range: Optional[Tuple[str, str]] = None,
    ) -> gpd.GeoDataFrame:
        # `now` belongs to the shared Provider protocol. Cubes evaluates the
        # relative one-hour window server-side, so no client timestamp is sent.
        database = quote(cubes_database_name(layer), safe="")
        path = f"/cube/v1/{database}"
        metadata = self._get_metadata(layer)
        parameters = _metadata_parameters(metadata)
        with self._client() as client:
            rows = self._fetch_rows(
                client, path, parameters, geometry, _results_limit(metadata), limit,
                now, temporal_range,
            )
        self._schema_cache[layer.id] = _infer_schema(layer.id, rows)
        return _rows_to_gdf(rows[:limit] if limit is not None else rows)

    def _fetch_rows(
        self,
        client: httpx.Client,
        path: str,
        parameters: List[LayerParameter],
        geometry: Optional[BaseGeometry],
        results_limit: int,
        requested_limit: Optional[int],
        now: Optional[datetime],
        temporal_range: Optional[Tuple[str, str]],
    ) -> List[dict]:
        rows = self._post_rows(
            client, path, _query_body(geometry, parameters, now, temporal_range))
        if requested_limit is not None or len(rows) < results_limit:
            return rows
        if geometry is None:
            raise ProviderError(
                f"Cubes reached its {results_limit} result limit without a boundary"
            )
        logger.info("Cubes result cap reached; splitting boundary into chunks")
        return self._fetch_spatial_chunks(
            client, path, parameters, geometry, results_limit, now,
            temporal_range, depth=0,
        )

    def _fetch_spatial_chunks(
        self,
        client: httpx.Client,
        path: str,
        parameters: List[LayerParameter],
        geometry: BaseGeometry,
        results_limit: int,
        now: Optional[datetime],
        temporal_range: Optional[Tuple[str, str]],
        depth: int,
    ) -> List[dict]:
        rows: List[dict] = []
        for chunk in _spatial_chunks(geometry):
            chunk_rows = self._fetch_chunk(
                client, path, parameters, chunk, results_limit, now,
                temporal_range, depth)
            rows.extend(chunk_rows)
            self._validate_row_count(rows)
        return _deduplicate_rows(rows)

    def _fetch_chunk(self, client: httpx.Client, path: str,
                     parameters: List[LayerParameter], geometry: BaseGeometry,
                     results_limit: int, now: Optional[datetime],
                     temporal_range: Optional[Tuple[str, str]],
                     depth: int) -> List[dict]:
        rows = self._post_rows(
            client, path, _query_body(geometry, parameters, now, temporal_range))
        if len(rows) < results_limit:
            return rows
        if depth >= _MAX_CHUNK_DEPTH:
            raise ProviderError("Cubes result chunks remain capped; narrow the map boundary")
        return self._fetch_spatial_chunks(
            client, path, parameters, geometry, results_limit, now,
            temporal_range, depth + 1)

    @staticmethod
    def _validate_row_count(rows: List[dict]) -> None:
        if len(rows) > _MAX_FETCHED_ROWS:
            raise ProviderError(
                f"Cubes returned more than the {_MAX_FETCHED_ROWS} row safety limit")

    @staticmethod
    def _post_rows(client: httpx.Client, path: str, body: dict) -> List[dict]:
        try:
            response = client.post(path, json=body)
            response.raise_for_status()
            return _records(response.json())
        except httpx.HTTPError as exc:
            raise ProviderError(f"Cubes request failed ({path}): {exc}")
        except ValueError as exc:
            raise ProviderError(f"Cubes returned invalid JSON ({path}): {exc}")

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

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self._base_url(), headers=self._headers(),
                            timeout=_TIMEOUT_SECONDS,
                            verify=self._store.get().cubes_verify_tls,
                            transport=self._transport)

    def _get_metadata(self, layer: LayerMeta) -> dict:
        cached = self._metadata_cache.get(layer.id)
        if cached is not None:
            return cached
        database = quote(cubes_database_name(layer), safe="")
        path = f"/cube/v1/{database}"
        try:
            with self._client() as client:
                response = client.get(path)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(f"Cubes metadata request failed ({path}): {exc}")
        if not isinstance(payload, dict):
            raise ProviderError("Cubes metadata response must be a JSON object")
        if "Parameters" not in payload:
            payload["Parameters"] = self._get_parameters(database)
        self._metadata_cache[layer.id] = payload
        return payload

    def _get_parameters(self, database: str) -> List[dict]:
        path = f"/cube/v1/{database}/parameters"
        try:
            with self._client() as client:
                response = client.get(path)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(f"Cubes parameters request failed ({path}): {exc}")
        if isinstance(payload, dict):
            payload = payload.get("Parameters") or payload.get("parameters")
        if not isinstance(payload, list):
            raise ProviderError("Cubes parameters response must be a JSON array")
        return [item for item in payload if isinstance(item, dict)]
