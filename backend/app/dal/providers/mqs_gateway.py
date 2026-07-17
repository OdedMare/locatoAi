"""MQS HTTP boundary and basic pagination."""

import logging
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import parse_qs, urlparse

import httpx
from shapely.geometry.base import BaseGeometry

from app.common.errors.provider_error import ProviderError
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.providers.mqs_entity_mapper import MqsEntityMapper
from app.dal.providers.mqs_filter_builder import MqsFilterBuilder


class MqsGateway:
    PAGE_SIZE = 10000
    MAX_FEATURES = 50000
    _TIMEOUT_SECONDS = 30
    _ENTITY_LIST_KEYS = (
        "entities_list", "EntitiesList", "features", "Features", "entities",
        "Entities", "data", "Data", "results", "Results", "items", "Items",
    )
    _TOTAL_KEYS = (
        "total_entities", "TotalEntities", "total", "Total", "count", "Count",
    )
    _LAYER_LIST_KEYS = ("layers_list", "LayersList", "layers", "Layers")

    def __init__(
        self,
        settings_store: RuntimeSettingsStore,
        mapper: MqsEntityMapper,
        filters: MqsFilterBuilder,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self._store = settings_store
        self._mapper = mapper
        self._filters = filters
        self._transport = transport
        self._logger = logging.getLogger(__name__)

    def client(self) -> httpx.Client:
        settings = self._store.get()
        if not settings.mqs_base_url:
            raise ProviderError(
                "MQS base URL is not configured — set mqs_base_url in the settings panel"
            )
        return httpx.Client(
            base_url=settings.mqs_base_url,
            timeout=self._TIMEOUT_SECONDS,
            verify=settings.mqs_verify_tls,
            transport=self._transport,
            headers=self._headers(settings.mqs_user_id),
        )

    def list_layers(self) -> List[dict]:
        with self.client() as client:
            payload = self.get_json(client, "/MoriaProject/Layers")
        layers = self._mapper.find_list(payload, self._LAYER_LIST_KEYS)
        if layers is None:
            raise ProviderError(
                "MQS returned an unrecognized layer-list response from /MoriaProject/Layers"
            )
        return layers

    def entities_page(
        self, client: httpx.Client, layer_id: str, params: Optional[dict],
        geometry: Optional[BaseGeometry] = None,
        attribute_filters: Optional[Sequence[Tuple[str, str]]] = None,
    ) -> Tuple[List[dict], Optional[str]]:
        entities, next_page, _ = self.entities_page_with_meta(
            client, layer_id, params, geometry, attribute_filters
        )
        return entities, next_page

    def entities_page_with_meta(
        self, client: httpx.Client, layer_id: str, params: Optional[dict],
        geometry: Optional[BaseGeometry] = None,
        attribute_filters: Optional[Sequence[Tuple[str, str]]] = None,
    ) -> Tuple[List[dict], Optional[str], Optional[int]]:
        path = f"/MoriaProject/{layer_id}/Entities"
        payload = self._entities_payload(
            client, path, params, geometry, attribute_filters
        )
        entities = self._mapper.find_list(payload, self._ENTITY_LIST_KEYS)
        if entities is None:
            raise ProviderError(
                f"MQS layer {layer_id} returned an unrecognized Entities response shape"
            )
        return entities, self._next_page(payload), self._response_total(payload)

    def iter_all_entities(
        self, client: httpx.Client, layer_id: str,
        geometry: Optional[BaseGeometry] = None, limit: Optional[int] = None,
        max_features: Optional[int] = MAX_FEATURES,
        attribute_filters: Optional[Sequence[Tuple[str, str]]] = None,
    ) -> Iterable[dict]:
        page_size = min(self.PAGE_SIZE, limit) if limit is not None else self.PAGE_SIZE
        params = {"from": 0, "to": page_size}
        fetched = 0
        while True:
            entities, next_page = self.entities_page(
                client, layer_id, params, geometry, attribute_filters
            )
            fetched += len(entities)
            yield from self._limited_page(entities, fetched, limit)
            if limit is not None and fetched >= limit:
                return
            self._validate_feature_count(layer_id, fetched, max_features)
            if next_page is None:
                return
            params = self.next_page_params(next_page)

    def entity_detail(
        self, client: httpx.Client, layer_id: str, entity: dict
    ) -> dict:
        if self._mapper.first(entity, self._mapper.PROPERTY_LIST_KEYS) is not None:
            return entity
        entity_id = self._mapper.entity_id(entity)
        if entity_id is None:
            self._logger.warning("MQS layer %s: entity has no entity_id", layer_id)
            return entity
        payload = self._safe_detail(client, layer_id, entity_id)
        detail = self._detail_object(payload)
        if detail is None:
            return entity
        merged = dict(entity)
        merged.update(detail)
        return merged

    def get_json(
        self, client: httpx.Client, path: str, params: Optional[dict] = None
    ) -> object:
        try:
            response = client.get(path, params=params)
            self._logger.info("MQS GET %s -> %s", response.request.url, response.status_code)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"MQS request failed ({path}): {exc}") from exc
        except ValueError as exc:
            raise ProviderError(f"MQS returned invalid JSON ({path}): {exc}") from exc

    def post_json(
        self, client: httpx.Client, path: str, body: dict,
        params: Optional[dict] = None,
    ) -> object:
        try:
            response = client.post(path, json=body, params=params)
            self._logger.info("MQS POST %s -> %s", response.request.url, response.status_code)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"MQS request failed ({path}): {exc}") from exc
        except ValueError as exc:
            raise ProviderError(f"MQS returned invalid JSON ({path}): {exc}") from exc

    @staticmethod
    def next_page_params(next_page_url: str) -> dict:
        query = parse_qs(urlparse(next_page_url).query)
        return {key: values[0] for key, values in query.items() if values}

    def _entities_payload(
        self, client, path, params, geometry, attribute_filters,
    ) -> object:
        body = self._filters.build(geometry, attribute_filters)
        if body is not None:
            return self.post_json(client, path, body, params)
        return self.get_json(client, path, params)

    @staticmethod
    def _next_page(payload: object) -> Optional[str]:
        value = payload.get("next_page") if isinstance(payload, dict) else None
        return value if isinstance(value, str) and value else None

    def _response_total(self, payload: object) -> Optional[int]:
        if not isinstance(payload, dict):
            return None
        value = self._mapper.first(payload, self._TOTAL_KEYS)
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _headers(user_id: Optional[str]) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if user_id:
            headers["User_ID"] = user_id
        return headers

    @staticmethod
    def _limited_page(
        entities: List[dict], fetched: int, limit: Optional[int]
    ) -> Iterable[dict]:
        if limit is None:
            return entities
        return entities[:limit - (fetched - len(entities))]

    @staticmethod
    def _validate_feature_count(
        layer_id: str, fetched: int, max_features: Optional[int]
    ) -> None:
        if max_features is not None and fetched > max_features:
            raise ProviderError(
                f"MQS layer {layer_id} returned more than the {max_features} "
                "feature limit — narrow the layer or raise the cap"
            )

    def _safe_detail(self, client, layer_id: str, entity_id: str) -> object:
        path = f"/MoriaProject/{layer_id}/EntityInfo/{entity_id}"
        try:
            return self.get_json(client, path)
        except ProviderError as exc:
            self._logger.warning(
                "MQS entity detail failed layer=%s entity=%s; using list-entity fields only: %s",
                layer_id, entity_id, exc,
            )
            return None

    def _detail_object(self, payload: object) -> Optional[dict]:
        if not isinstance(payload, dict):
            return None
        for key in ("entity", "Entity", "data", "Data"):
            if isinstance(payload.get(key), dict):
                return payload[key]
        return payload
