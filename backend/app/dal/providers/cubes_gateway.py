"""Cubes HTTP access and capped-result recovery."""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

import httpx
from shapely.geometry.base import BaseGeometry

from app.bl.ports.layer_meta import LayerMeta
from app.bl.ports.layer_parameter import LayerParameter
from app.bl.ports.layer_parameter_option import LayerParameterOption
from app.common.errors.provider_error import ProviderError
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.providers.cubes_query_builder import CubesQueryBuilder
from app.dal.providers.cubes_schema_mapper import CubesSchemaMapper
from app.dal.providers.cubes_source import CubesSource


class CubesGateway:
    _TIMEOUT_SECONDS = 30
    _MAX_CHUNK_DEPTH = 5
    _MAX_ROWS = 100000

    def __init__(
        self,
        settings_store: RuntimeSettingsStore,
        source: CubesSource,
        query_builder: CubesQueryBuilder,
        mapper: CubesSchemaMapper,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self._store = settings_store
        self._source = source
        self._query = query_builder
        self._mapper = mapper
        self._transport = transport
        self._metadata_cache: Dict[str, dict] = {}
        self._logger = logging.getLogger(__name__)

    def set_transport(self, transport: Optional[httpx.BaseTransport]) -> None:
        self._transport = transport

    def metadata(self, layer: LayerMeta) -> dict:
        database = quote(self._source.database_name(layer), safe="")
        cached = self._metadata_cache.get(database)
        if cached is not None:
            return cached
        payload = self._get_json(f"/cube/v1/{database}", "metadata")
        if not isinstance(payload, dict):
            raise ProviderError("Cubes metadata response must be a JSON object")
        if not isinstance(payload.get("Parameters"), list):
            payload["Parameters"] = self._parameters(database)
        self._metadata_cache[database] = payload
        return payload

    def autocomplete(
        self, layer: LayerMeta, parameter_name: str
    ) -> List[LayerParameterOption]:
        database = quote(self._source.database_name(layer), safe="")
        parameter = quote(parameter_name, safe="")
        path = f"/cube/v1/{database}/autocomplete/{parameter}"
        payload = self._post_json(path, {}, "autocomplete")
        if not isinstance(payload, list):
            raise ProviderError("Cubes autocomplete response must be a JSON array")
        return [
            LayerParameterOption(
                value=str(item["Value"]), name=str(item.get("Name") or "")
            )
            for item in payload
            if isinstance(item, dict) and item.get("Value") not in (None, "")
        ]

    def fetch_rows(
        self,
        layer: LayerMeta,
        parameters: List[LayerParameter],
        geometry: Optional[BaseGeometry],
        results_limit: int,
        requested_limit: Optional[int],
        now: Optional[datetime],
        temporal_range: Optional[Tuple[str, str]],
        query_mode: str,
    ) -> List[dict]:
        database = quote(self._source.database_name(layer), safe="")
        path = f"/cube/v1/{database}"
        with self._client() as client:
            return self._fetch(
                client, path, parameters, geometry, results_limit,
                requested_limit, now, temporal_range, query_mode,
            )

    def _fetch(
        self, client: httpx.Client, path: str, parameters: List[LayerParameter],
        geometry: Optional[BaseGeometry], results_limit: int,
        requested_limit: Optional[int], now: Optional[datetime],
        temporal_range: Optional[Tuple[str, str]], query_mode: str,
    ) -> List[dict]:
        body = self._query.build(geometry, parameters, now, temporal_range, query_mode)
        rows = self._post_rows(client, path, body)
        if requested_limit is not None or len(rows) < results_limit:
            return rows
        if geometry is not None:
            self._logger.info("Cubes result cap reached; splitting boundary into chunks")
            return self._spatial_chunks(
                client, path, parameters, geometry, results_limit,
                now, temporal_range, query_mode, 0,
            )
        return self._split_unbounded(
            client, path, parameters, results_limit, body, query_mode, rows
        )

    def _split_unbounded(
        self, client, path, parameters, results_limit, body, query_mode, rows,
    ) -> List[dict]:
        window_key = self._query.match_window_key(body)
        if window_key is None:
            return rows
        self._logger.info("Cubes result cap reached; splitting time window into chunks")
        window = body[window_key]["From"], body[window_key]["To"]
        return self._temporal_chunks(
            client, path, parameters, results_limit, window, query_mode, 0
        )

    def _spatial_chunks(
        self, client, path, parameters, geometry, results_limit,
        now, temporal_range, query_mode, depth,
    ) -> List[dict]:
        rows: List[dict] = []
        for chunk in self._query.spatial_chunks(geometry):
            rows.extend(self._spatial_chunk(
                client, path, parameters, chunk, results_limit,
                now, temporal_range, query_mode, depth,
            ))
            self._validate_count(rows)
        return self._mapper.deduplicate(rows)

    def _spatial_chunk(
        self, client, path, parameters, geometry, results_limit,
        now, temporal_range, query_mode, depth,
    ) -> List[dict]:
        body = self._query.build(geometry, parameters, now, temporal_range, query_mode)
        rows = self._post_rows(client, path, body)
        if len(rows) < results_limit:
            return rows
        if depth >= self._MAX_CHUNK_DEPTH:
            raise ProviderError("Cubes result chunks remain capped; narrow the map boundary")
        return self._spatial_chunks(
            client, path, parameters, geometry, results_limit,
            now, temporal_range, query_mode, depth + 1,
        )

    def _temporal_chunks(
        self, client, path, parameters, results_limit, window, query_mode, depth,
    ) -> List[dict]:
        rows: List[dict] = []
        for half in self._query.split_temporal_range(*window):
            rows.extend(self._temporal_chunk(
                client, path, parameters, results_limit, half, query_mode, depth
            ))
            self._validate_count(rows)
        return self._mapper.deduplicate(rows)

    def _temporal_chunk(
        self, client, path, parameters, results_limit, window, query_mode, depth,
    ) -> List[dict]:
        body = self._query.build(None, parameters, None, window, query_mode)
        rows = self._post_rows(client, path, body)
        if len(rows) < results_limit:
            return rows
        if depth >= self._MAX_CHUNK_DEPTH:
            raise ProviderError("Cubes result chunks remain capped; narrow the time window")
        return self._temporal_chunks(
            client, path, parameters, results_limit, window, query_mode, depth + 1
        )

    def _post_rows(self, client: httpx.Client, path: str, body: dict) -> List[dict]:
        try:
            response = client.post(path, json=body)
            response.raise_for_status()
            return self._mapper.records(response.json())
        except httpx.HTTPError as exc:
            raise ProviderError(f"Cubes request failed ({path}): {exc}") from exc
        except ValueError as exc:
            raise ProviderError(f"Cubes returned invalid JSON ({path}): {exc}") from exc

    def _get_json(self, path: str, request_name: str) -> object:
        try:
            with self._client() as client:
                response = client.get(path)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(f"Cubes {request_name} request failed ({path}): {exc}")

    def _post_json(self, path: str, body: dict, request_name: str) -> object:
        try:
            with self._client() as client:
                response = client.post(path, json=body)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(f"Cubes {request_name} request failed ({path}): {exc}")

    def _parameters(self, database: str) -> List[dict]:
        path = f"/cube/v1/{database}/parameters"
        payload = self._get_json(path, "parameters")
        if isinstance(payload, dict):
            payload = payload.get("Parameters") or payload.get("parameters")
        if not isinstance(payload, list):
            raise ProviderError("Cubes parameters response must be a JSON array")
        return [item for item in payload if isinstance(item, dict)]

    def _client(self) -> httpx.Client:
        settings = self._store.get()
        if not settings.cubes_base_url:
            raise ProviderError("Cubes base URL is not configured — set cubes_base_url")
        if not settings.cubes_token:
            raise ProviderError("Cubes authorization token is not configured — set cubes_token")
        return httpx.Client(
            base_url=settings.cubes_base_url,
            headers=self._headers(settings.cubes_token),
            timeout=self._TIMEOUT_SECONDS,
            verify=settings.cubes_verify_tls,
            transport=self._transport,
        )

    @staticmethod
    def _headers(token: str) -> dict:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": token,
        }

    def _validate_count(self, rows: List[dict]) -> None:
        if len(rows) > self._MAX_ROWS:
            raise ProviderError(
                f"Cubes returned more than the {self._MAX_ROWS} row safety limit"
            )
