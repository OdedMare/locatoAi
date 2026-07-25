"""MQS HTTP provider with pagination, splitting, and enrichment."""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Iterable, List, Optional, Sequence, Set, Tuple
from urllib.parse import parse_qs, quote, urlparse

import geopandas as gpd
import httpx
from shapely.geometry.base import BaseGeometry

from app.bl.catalog.models.layer_meta import LayerMeta
from app.bl.catalog.models.layer_schema import LayerSchema
from app.bl.providers.provider import ATTRIBUTE_FILTER_PUSHDOWN
from app.common.errors.provider_error import ProviderError
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.providers.mqs.mapper import MqsMapper

_PAGE_SIZE = 10000
_MAX_FEATURES_PER_LAYER = 10000


class MqsProvider:
    """Perform MQS HTTP; all request/response shapes live in ``MqsMapper``."""

    capabilities = frozenset({ATTRIBUTE_FILTER_PUSHDOWN})
    _MAX_FEATURES = 50000
    _MAX_SPLIT_DEPTH = 4
    _PROBE_PAGES = 2
    _METADATA_SAMPLE_SIZE = 10
    _ENTITY_LIST_KEYS = (
        "entities_list", "EntitiesList", "features", "Features", "entities",
        "Entities", "data", "Data", "results", "Results", "items", "Items",
    )
    _TOTAL_KEYS = (
        "total_entities", "TotalEntities", "total", "Total", "count", "Count",
    )
    _LAYER_LIST_KEYS = ("layers_list", "LayersList", "layers", "Layers")

    def __init__(
        self, settings_store: RuntimeSettingsStore,
        transport: Optional[httpx.BaseTransport] = None,
        detail_concurrency: int = 16,
    ) -> None:
        self._store = settings_store
        self._transport = transport
        self._detail_concurrency = max(1, detail_concurrency)
        self._mapper = MqsMapper()
        self._logger = logging.getLogger(__name__)

    def describe_schema(
        self, layer: LayerMeta, geometry=None,
    ) -> LayerSchema:
        layer_id = self._mapper.layer_id(layer)
        with self._client() as client:
            entities = self._enriched(client, layer_id, limit=20)
            return self._mapper.schema(layer, layer_id, entities)

    def fetch_features(
        self, layer: LayerMeta, now: Optional[datetime] = None,
        geometry: Optional[BaseGeometry] = None,
        limit: Optional[int] = None,
        attribute_filters: Optional[Sequence[Tuple[str, str]]] = None,
        temporal_range: Optional[Tuple[str, str]] = None,
    ) -> gpd.GeoDataFrame:
        layer_id = self._mapper.layer_id(layer)
        with self._client() as client:
            entities = self._enriched(
                client, layer_id, geometry, limit, attribute_filters,
            )
            return self._mapper.to_gdf(layer_id, entities, geometry)

    def sample_for_metadata(
        self, layer: LayerMeta, limit: int = 100,
    ) -> Tuple[gpd.GeoDataFrame, LayerSchema]:
        layer_id = self._mapper.layer_id(layer)
        sample_size = min(limit, self._METADATA_SAMPLE_SIZE)
        business, fallback = [], []
        with self._client() as client:
            entities = self._query(client, layer_id, limit=sample_size)
            self._collect_metadata(
                client, layer_id, entities, business, fallback,
            )
        sampled = (
            business[:self._METADATA_SAMPLE_SIZE] if business else fallback
        )
        return (
            self._mapper.to_gdf(layer_id, sampled),
            self._mapper.schema(layer, layer_id, sampled),
        )

    def sample_field_values(
        self, layer: LayerMeta, field: str, limit: int = 20,
    ) -> List[str]:
        layer_id = self._mapper.layer_id(layer)
        size = min(_PAGE_SIZE, max(limit * 5, 20))
        with self._client() as client:
            entities, _ = self._entities_page(
                client, layer_id, {"from": 0, "to": size},
            )
            values = self._field_values(
                client, layer_id, entities, field, limit,
            )
        return values[:limit]

    def list_remote_layers(self) -> List[dict]:
        with self._client() as client:
            payload = self._request_json(client, "GET", "/MoriaProject/Layers")
        layers = self._mapper.find_list(payload, self._LAYER_LIST_KEYS)
        if layers is None:
            raise ProviderError(
                "MQS returned an unrecognized layer-list response "
                "from /MoriaProject/Layers"
            )
        return layers

    def _client(self) -> httpx.Client:
        settings = self._store.get()
        if not settings.mqs_base_url:
            raise ProviderError(
                "MQS base URL is not configured — set mqs_base_url "
                "in the settings panel"
            )
        headers = {"Accept": "application/json"}
        if settings.mqs_user_id:
            headers["User_ID"] = settings.mqs_user_id
        return httpx.Client(
            base_url=settings.mqs_base_url, timeout=None,
            verify=settings.mqs_verify_tls, transport=self._transport,
            headers=headers,
        )

    def _request_json(
        self, client: httpx.Client, method: str, path: str,
        params: Optional[dict] = None, body: Optional[dict] = None,
    ) -> object:
        try:
            response = client.request(method, path, params=params, json=body)
            self._logger.info(
                "MQS %s %s -> %s", method, response.request.url,
                response.status_code,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise self._status_error(path, exc) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                "MQS request failed (%s): %s" % (path, exc)) from exc
        except ValueError as exc:
            raise ProviderError(
                "MQS returned invalid JSON (%s): %s" % (path, exc)) from exc

    def _entities_page(
        self, client, layer_id, params, geometry=None, attribute_filters=None,
    ) -> Tuple[List[dict], Optional[str]]:
        entities, next_page, _ = self._entities_page_with_meta(
            client, layer_id, params, geometry, attribute_filters,
        )
        return entities, next_page

    def _entities_page_with_meta(
        self, client, layer_id, params, geometry=None, attribute_filters=None,
    ) -> Tuple[List[dict], Optional[str], Optional[int]]:
        path = "/MoriaProject/%s/Entities" % layer_id
        body = self._mapper.filter_body(geometry, attribute_filters)
        payload = self._request_json(
            client, "POST", path, params=params, body=body,
        )
        entities = self._mapper.find_list(payload, self._ENTITY_LIST_KEYS)
        if entities is None:
            raise ProviderError(
                "MQS layer %s returned an unrecognized Entities response shape"
                % layer_id
            )
        return entities, self._next_page(payload), self._response_total(payload)

    def _all_entities(
        self, client, layer_id, geometry=None, limit=None,
        max_features=None, attribute_filters=None,
    ) -> Iterable[dict]:
        size = min(_PAGE_SIZE, limit) if limit is not None else _PAGE_SIZE
        params, fetched = {"from": 0, "to": size}, 0
        while True:
            entities, next_page = self._entities_page(
                client, layer_id, params, geometry, attribute_filters,
            )
            fetched += len(entities)
            if limit is not None and fetched >= limit:
                yield from entities[:limit - (fetched - len(entities))]
                return
            self._validate_count(layer_id, fetched, max_features)
            yield from entities
            if next_page is None:
                return
            params = self._next_page_params(next_page)

    def _query(
        self, client, layer_id, geometry=None, limit=None,
        attribute_filters=None,
    ) -> Iterable[dict]:
        if geometry is not None and limit is None:
            yield from self._bounded_query(
                client, layer_id, geometry, attribute_filters,
            )
            return
        cap = (
            _MAX_FEATURES_PER_LAYER if limit is None else self._MAX_FEATURES
        )
        yield from self._all_entities(
            client, layer_id, geometry, limit, cap, attribute_filters,
        )

    def _enriched(
        self, client, layer_id, geometry=None, limit=None,
        attribute_filters=None,
    ) -> Iterable[dict]:
        entities = self._query(
            client, layer_id, geometry, limit, attribute_filters,
        )
        for batch in self._batched(entities):
            yield from self._enrich_batch(client, layer_id, batch)

    def _enrich_batch(
        self, client, layer_id: str, entities: Sequence[dict],
    ) -> List[dict]:
        if self._detail_concurrency == 1 or len(entities) == 1:
            return [
                self._entity_detail(client, layer_id, item) for item in entities
            ]
        with ThreadPoolExecutor(
            max_workers=self._detail_concurrency
        ) as executor:
            return list(executor.map(
                lambda item: self._entity_detail(client, layer_id, item),
                entities,
            ))

    def _entity_detail(self, client, layer_id: str, entity: dict) -> dict:
        if self._mapper.first(
            entity, self._mapper.PROPERTY_LIST_KEYS,
        ) is not None:
            return entity
        entity_id = self._mapper.entity_id(entity)
        if entity_id is None:
            self._logger.warning(
                "MQS layer %s: entity has no entity_id", layer_id)
            return entity
        detail = self._detail_object(
            self._safe_detail(client, layer_id, entity_id)
        )
        if detail is None:
            return entity
        return dict(entity, **detail)

    def _safe_detail(
        self, client, layer_id: str, entity_id: str,
    ) -> object:
        path = (
            "/MoriaProject/%s/EntityInfo/%s" % (
                quote(layer_id.lstrip("/"), safe=""),
                quote(entity_id.lstrip("/"), safe=""),
            )
        )
        try:
            return self._request_json(client, "GET", path)
        except ProviderError as exc:
            self._logger.warning(
                "MQS entity detail failed layer=%s entity=%s; "
                "using list-entity fields only: %s", layer_id, entity_id, exc,
            )
            return None

    def _bounded_query(
        self, client, layer_id, geometry, attribute_filters,
    ) -> Iterable[dict]:
        seen_ids: Set[str] = set()
        fetched = 0
        entities = self._geometry_region(
            client, layer_id, geometry, 0, None, None, attribute_filters,
        )
        for entity in entities:
            entity_id = self._mapper.entity_id(entity)
            if entity_id is not None and entity_id in seen_ids:
                continue
            if entity_id is not None:
                seen_ids.add(entity_id)
            fetched += 1
            self._validate_layer_cap(layer_id, fetched)
            yield entity

    def _geometry_region(
        self, client, layer_id, geometry, depth, parent_total,
        parent_observed, attribute_filters,
    ) -> Iterable[dict]:
        probe = self._probe_region(client, layer_id, geometry, attribute_filters)
        buffered, next_page, total, visited = probe
        chunks = self._split_chunks(
            geometry, depth, total, next_page, len(buffered),
            parent_total, parent_observed,
        )
        if chunks:
            self._log_split(layer_id, depth, total, len(buffered))
            for chunk in chunks:
                yield from self._geometry_region(
                    client, layer_id, chunk, depth + 1, total,
                    len(buffered), attribute_filters)
            return
        yield from buffered
        yield from self._remaining_pages(
            client, layer_id, geometry, attribute_filters, next_page, visited)

    def _probe_region(
        self, client, layer_id, geometry, attribute_filters,
    ):
        params = {"from": 0, "to": _PAGE_SIZE}
        buffered, visited = [], set()
        total, next_page = None, None
        for index in range(self._PROBE_PAGES):
            entities, next_page, page_total = self._entities_page_with_meta(
                client, layer_id, params, geometry, attribute_filters,
            )
            buffered.extend(entities)
            total = page_total if total is None else total
            if next_page is None or total is not None:
                break
            if index + 1 < self._PROBE_PAGES:
                self._remember_page(layer_id, next_page, visited)
                params = self._next_page_params(next_page)
        return buffered, next_page, total, visited

    def _remaining_pages(
        self, client, layer_id, geometry, attribute_filters,
        next_page, visited,
    ) -> Iterable[dict]:
        while next_page is not None:
            self._remember_page(layer_id, next_page, visited)
            params = self._next_page_params(next_page)
            entities, next_page, _ = self._entities_page_with_meta(
                client, layer_id, params, geometry, attribute_filters,
            )
            yield from entities

    def _split_chunks(
        self, geometry, depth, total, next_page, observed,
        parent_total, parent_observed,
    ) -> List[BaseGeometry]:
        if not self._should_split(
            depth, total, next_page, observed, parent_total, parent_observed,
        ):
            return []
        chunks = self._mapper.split(geometry)
        return chunks if len(chunks) > 1 else []

    def _should_split(
        self, depth, total, next_page, observed, parent_total, parent_observed,
    ) -> bool:
        total_shrank = (
            total is not None and parent_total is not None
            and total < parent_total
        )
        observed_shrank = (
            parent_observed is not None and observed < parent_observed
        )
        overloaded = (
            (total is not None and total > _PAGE_SIZE)
            or (total is None and next_page is not None)
        )
        return (
            depth < self._MAX_SPLIT_DEPTH and overloaded
            and (depth == 0 or total_shrank or observed_shrank)
        )

    def _collect_metadata(
        self, client, layer_id, entities, business, fallback,
    ) -> None:
        for batch in self._batched(entities, size=1):
            for entity in self._enrich_batch(client, layer_id, batch):
                if self._mapper.to_record(entity) is None:
                    continue
                if len(fallback) < self._METADATA_SAMPLE_SIZE:
                    fallback.append(entity)
                if self._mapper.property_attributes(entity):
                    business.append(entity)
            if len(business) >= self._METADATA_SAMPLE_SIZE:
                return

    def _field_values(
        self, client, layer_id, entities, field, limit,
    ) -> List[str]:
        values: List[str] = []
        for batch in self._batched(entities):
            for entity in self._enrich_batch(client, layer_id, batch):
                record = self._mapper.to_record(entity)
                value = record[1].get(field) if record is not None else None
                if value is not None:
                    text = str(value)[:40]
                    if text not in values:
                        values.append(text)
                if len(values) >= limit:
                    return values
        return values

    def _batched(
        self, entities: Iterable[dict], size: Optional[int] = None,
    ) -> Iterable[List[dict]]:
        batch_size = max(1, size or self._detail_concurrency)
        batch: List[dict] = []
        for entity in entities:
            batch.append(entity)
            if len(batch) >= batch_size:
                yield batch
                batch = []
        if batch:
            yield batch

    def _response_total(self, payload: object) -> Optional[int]:
        if not isinstance(payload, dict):
            return None
        value = self._mapper.first(payload, self._TOTAL_KEYS)
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _next_page(payload: object) -> Optional[str]:
        value = payload.get("next_page") if isinstance(payload, dict) else None
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _next_page_params(next_page_url: str) -> dict:
        query = parse_qs(urlparse(next_page_url).query)
        return {key: values[0] for key, values in query.items() if values}

    @staticmethod
    def _detail_object(payload: object) -> Optional[dict]:
        if not isinstance(payload, dict):
            return None
        for key in ("entity", "Entity", "data", "Data"):
            if isinstance(payload.get(key), dict):
                return payload[key]
        return payload

    @staticmethod
    def _remember_page(layer_id: str, next_page: str, visited: set) -> None:
        if next_page in visited:
            raise ProviderError(
                "MQS layer %s returned a repeated next_page" % layer_id)
        visited.add(next_page)

    @staticmethod
    def _validate_count(
        layer_id: str, fetched: int, max_features: Optional[int],
    ) -> None:
        if max_features is not None and fetched > max_features:
            raise ProviderError(
                "MQS layer %s returned more than the %s feature limit — "
                "narrow the layer or raise the cap" % (
                    layer_id, max_features,
                )
            )

    @staticmethod
    def _validate_layer_cap(layer_id: str, fetched: int) -> None:
        if fetched > _MAX_FEATURES_PER_LAYER:
            raise ProviderError(
                "MQS layer %s returned more than the %s per-layer feature "
                "limit inside the requested geometry — narrow the boundary"
                % (layer_id, _MAX_FEATURES_PER_LAYER)
            )

    def _log_split(
        self, layer_id: str, depth: int, total, observed: int,
    ) -> None:
        self._logger.info(
            "MQS geo split layer=%s depth=%d total=%s buffered=%d",
            layer_id, depth, total, observed,
        )

    @staticmethod
    def _status_error(
        path: str, exc: httpx.HTTPStatusError,
    ) -> ProviderError:
        response = exc.response
        message = (
            "MQS request failed (%s): upstream returned %s %s"
            % (path, response.status_code, response.reason_phrase)
        )
        body = " ".join(response.text.split())[:300]
        if body:
            message += " — " + body
        if (
            response.status_code >= 500
            and "User_ID" not in response.request.headers
        ):
            message += (
                " — MQS User_ID is not configured; this endpoint may require it"
            )
        return ProviderError(message)


_mapper_compat = MqsMapper()
mqs_layer_id = _mapper_compat.layer_id
