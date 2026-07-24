

import time
from typing import Dict, List, Tuple

from app.bl.catalog.models.layer_meta import LayerMeta
from app.bl.catalog.models.layer_schema import LayerSchema
from app.bl.catalog.layers_repository import LayersRepository
from app.bl.providers.registry import ProviderRegistry
from app.common.errors.layer_not_found_error import LayerNotFoundError
from app.common.errors.provider_error import ProviderError


class CatalogService:
    def __init__(
        self,
        repository: LayersRepository,
        providers: ProviderRegistry,
        schema_ttl_seconds: int = 3600,
    ):
        self._repository = repository
        self._providers = providers
        self._schema_ttl = schema_ttl_seconds
        # {layer_id: (schema, fetched_at_monotonic)}
        self._schema_cache: Dict[str, Tuple[LayerSchema, float]] = {}

    def list_layers(self) -> List[LayerMeta]:
        return self._repository.list_layers()

    def list_queryable_layers(self) -> List[LayerMeta]:
        return [
            layer for layer in self._repository.list_layers()
            if self._providers.has(layer.provider)
        ]

    def get_layer(self, layer_id: str) -> LayerMeta:
        layer = self._repository.get_layer(layer_id)
        if layer is None:
            raise LayerNotFoundError(layer_id)
        return layer

    def add_layer(self, layer: LayerMeta) -> LayerMeta:
        """Persist a new catalog layer through the repository port."""
        return self._repository.add_layer(layer)

    def update_layer_metadata(
        self, layer_id: str, name: str, description: str, tags: List[str],
    ) -> LayerMeta:
        self.get_layer(layer_id)
        updated = self._repository.update_layer_metadata(
            layer_id, name, description, tags
        )
        self._schema_cache.pop(layer_id, None)
        return updated

    def sample_field(self, layer_id: str, field: str, limit: int = 20) -> List[str]:
        layer = self.get_layer(layer_id)
        provider = self._providers.get(layer.provider)
        return provider.sample_field_values(layer, field, limit=limit)

    def get_schema(self, layer_id: str) -> LayerSchema:
        cached = self._schema_cache.get(layer_id)
        if self._is_fresh(cached):
            return cached[0]
        layer = self.get_layer(layer_id)
        provider = self._providers.get(layer.provider)
        try:
            schema = provider.describe_schema(layer)
        except Exception as exc:
            return self._stale_or_error(cached, layer, layer_id, exc)
        self._schema_cache[layer_id] = (schema, time.monotonic())
        return schema

    def _is_fresh(self, cached) -> bool:
        return (
            cached is not None
            and time.monotonic() - cached[1] < self._schema_ttl
        )

    @staticmethod
    def _stale_or_error(cached, layer, layer_id, error):
        if cached is not None:
            return cached[0]
        raise ProviderError(
            f"Provider '{layer.provider}' failed to describe layer "
            f"{layer_id}: {error}"
        ) from error
