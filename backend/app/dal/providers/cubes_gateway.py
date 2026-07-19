"""Cubes HTTP access and capped-result recovery."""

import logging
from datetime import datetime
from typing import List, Optional, Tuple
from urllib.parse import quote

import httpx
from shapely.geometry.base import BaseGeometry

from app.bl.ports.layer_meta import LayerMeta
from app.bl.ports.layer_parameter import LayerParameter
from app.common.errors.provider_error import ProviderError
from app.dal.providers.cubes_client_factory import CubesClientFactory
from app.dal.providers.cubes_query_builder import CubesQueryBuilder
from app.dal.providers.cubes_schema_mapper import CubesSchemaMapper
from app.dal.providers.cubes_source import CubesSource


class CubesGateway:
    _MAX_CHUNK_DEPTH = 5
    _MAX_ROWS = 100000

    def __init__(
        self,
        clients: CubesClientFactory,
        source: CubesSource,
        query_builder: CubesQueryBuilder,
        mapper: CubesSchemaMapper,
    ) -> None:
        self._clients = clients
        self._source = source
        self._query = query_builder
        self._mapper = mapper
        self._logger = logging.getLogger(__name__)

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
        with self._clients.create() as client:
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

    def _validate_count(self, rows: List[dict]) -> None:
        if len(rows) > self._MAX_ROWS:
            raise ProviderError(
                f"Cubes returned more than the {self._MAX_ROWS} row safety limit"
            )
