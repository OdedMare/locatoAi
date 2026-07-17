"""Stream, split, deduplicate, and enrich MQS entities."""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable, List, Optional, Sequence, Tuple

import httpx
from shapely.geometry.base import BaseGeometry

from app.common.errors.provider_error import ProviderError
from app.dal.providers.mqs_entity_mapper import MqsEntityMapper
from app.dal.providers.mqs_filter_builder import MqsFilterBuilder
from app.dal.providers.mqs_gateway import MqsGateway


class MqsEntityStream:
    MAX_FEATURES_PER_LAYER = 10000
    _MAX_SPLIT_DEPTH = 4
    _PROBE_PAGES = 2

    def __init__(
        self,
        gateway: MqsGateway,
        mapper: MqsEntityMapper,
        filters: MqsFilterBuilder,
        detail_concurrency: int,
    ) -> None:
        self._gateway = gateway
        self._mapper = mapper
        self._filters = filters
        self._detail_concurrency = max(1, detail_concurrency)
        self._logger = logging.getLogger(__name__)

    def enriched(
        self, client: httpx.Client, layer_id: str,
        geometry: Optional[BaseGeometry] = None, limit: Optional[int] = None,
        attribute_filters: Optional[Sequence[Tuple[str, str]]] = None,
    ) -> Iterable[dict]:
        pending: List[dict] = []
        entities = self.query(
            client, layer_id, geometry, limit, attribute_filters
        )
        for entity in entities:
            pending.append(entity)
            if len(pending) >= self._detail_concurrency:
                yield from self.enrich_batch(client, layer_id, pending)
                pending = []
        if pending:
            yield from self.enrich_batch(client, layer_id, pending)

    def query(
        self, client: httpx.Client, layer_id: str,
        geometry: Optional[BaseGeometry] = None, limit: Optional[int] = None,
        attribute_filters: Optional[Sequence[Tuple[str, str]]] = None,
    ) -> Iterable[dict]:
        if geometry is None or limit is not None:
            max_features = (
                self.MAX_FEATURES_PER_LAYER if limit is None
                else self._gateway.MAX_FEATURES
            )
            yield from self._gateway.iter_all_entities(
                client, layer_id, geometry, limit, max_features, attribute_filters
            )
            return
        yield from self._bounded_query(
            client, layer_id, geometry, attribute_filters
        )

    def enrich_batch(
        self, client: httpx.Client, layer_id: str, entities: Sequence[dict]
    ) -> List[dict]:
        if self._detail_concurrency == 1 or len(entities) == 1:
            return [self._gateway.entity_detail(client, layer_id, item)
                    for item in entities]
        with ThreadPoolExecutor(max_workers=self._detail_concurrency) as executor:
            return list(executor.map(
                lambda item: self._gateway.entity_detail(client, layer_id, item),
                entities,
            ))

    def batched(self, entities: Iterable[dict]) -> Iterable[List[dict]]:
        batch: List[dict] = []
        for entity in entities:
            batch.append(entity)
            if len(batch) >= self._detail_concurrency:
                yield batch
                batch = []
        if batch:
            yield batch

    def _bounded_query(
        self, client, layer_id, geometry, attribute_filters,
    ) -> Iterable[dict]:
        seen_ids = set()
        fetched = 0
        entities = self._geometry_region(
            client, layer_id, geometry, 0, None, None, attribute_filters
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
        self, client, layer_id, geometry, depth,
        parent_total, parent_observed, attribute_filters,
    ) -> Iterable[dict]:
        buffered, next_page, total, visited = self._probe_region(
            client, layer_id, geometry, attribute_filters
        )
        if self._should_split(
            depth, total, next_page, len(buffered), parent_total, parent_observed
        ):
            chunks = self._filters.split(geometry)
            if len(chunks) > 1:
                self._log_split(layer_id, depth, total, len(buffered))
                for chunk in chunks:
                    yield from self._geometry_region(
                        client, layer_id, chunk, depth + 1,
                        total, len(buffered), attribute_filters,
                    )
                return
        yield from buffered
        yield from self._remaining_pages(
            client, layer_id, geometry, attribute_filters, next_page, visited
        )

    def _probe_region(
        self, client, layer_id, geometry, attribute_filters,
    ):
        params = {"from": 0, "to": self._gateway.PAGE_SIZE}
        buffered: List[dict] = []
        total = None
        next_page = None
        visited = set()
        for index in range(self._PROBE_PAGES):
            entities, next_page, page_total = self._gateway.entities_page_with_meta(
                client, layer_id, params, geometry, attribute_filters
            )
            buffered.extend(entities)
            total = page_total if total is None else total
            if next_page is None or total is not None:
                break
            if index + 1 < self._PROBE_PAGES:
                self._remember_page(layer_id, next_page, visited)
                params = self._gateway.next_page_params(next_page)
        return buffered, next_page, total, visited

    def _remaining_pages(
        self, client, layer_id, geometry, attribute_filters, next_page, visited,
    ) -> Iterable[dict]:
        while next_page is not None:
            self._remember_page(layer_id, next_page, visited)
            params = self._gateway.next_page_params(next_page)
            entities, next_page, _ = self._gateway.entities_page_with_meta(
                client, layer_id, params, geometry, attribute_filters
            )
            yield from entities

    def _should_split(
        self, depth, total, next_page, observed, parent_total, parent_observed,
    ) -> bool:
        total_shrank = total is not None and parent_total is not None and total < parent_total
        observed_shrank = parent_observed is not None and observed < parent_observed
        region_shrank = depth == 0 or total_shrank or observed_shrank
        overloaded = (
            (total is not None and total > self._gateway.PAGE_SIZE)
            or (total is None and next_page is not None)
        )
        return depth < self._MAX_SPLIT_DEPTH and overloaded and region_shrank

    @staticmethod
    def _remember_page(layer_id: str, next_page: str, visited: set) -> None:
        if next_page in visited:
            raise ProviderError(f"MQS layer {layer_id} returned a repeated next_page")
        visited.add(next_page)

    def _validate_layer_cap(self, layer_id: str, fetched: int) -> None:
        if fetched > self.MAX_FEATURES_PER_LAYER:
            raise ProviderError(
                f"MQS layer {layer_id} returned more than the "
                f"{self.MAX_FEATURES_PER_LAYER} per-layer feature limit inside "
                "the requested geometry — narrow the boundary, add an attribute "
                "filter, or use an aggregation"
            )

    def _log_split(self, layer_id: str, depth: int, total, observed: int) -> None:
        self._logger.info(
            "MQS geo split layer=%s depth=%d total=%s buffered=%d",
            layer_id, depth, total, observed,
        )
