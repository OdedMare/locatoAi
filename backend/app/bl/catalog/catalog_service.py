

import time
from typing import Dict, List, Optional, Tuple

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
        # {(layer_id, boundary_wkb_or_None): (schema, fetched_at_monotonic)}
        self._schema_cache: Dict[
            Tuple[str, Optional[bytes]], Tuple[LayerSchema, float]
        ] = {}

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
        entity_field=None, display_field=None, profiles=None,
    ) -> LayerMeta:
        current = self.get_layer(layer_id)
        candidate = current.model_copy(update={
            "name": name, "description": description, "tags": tags,
            "entity_field": entity_field, "display_field": display_field,
            "profiles": profiles or [],
        })
        updated = self._repository.update_layer_metadata(
            LayerMeta.model_validate(candidate.model_dump())
        )
        self._schema_cache.pop(layer_id, None)
        return updated

    def delete_layer(self, layer_id: str) -> LayerMeta:
        deleted = self._repository.delete_layer(layer_id)
        if deleted is None:
            raise LayerNotFoundError(layer_id)
        # Keys are (layer_id, boundary): drop every boundary variant.
        for key in [key for key in self._schema_cache if key[0] == layer_id]:
            self._schema_cache.pop(key, None)
        return deleted

    def sample_field(self, layer_id: str, field: str, limit: int = 20) -> List[str]:
        layer = self.get_layer(layer_id)
        provider = self._providers.get(layer.provider)
        return provider.sample_field_values(layer, field, limit=limit)

    def get_schema(self, layer_id: str, geometry=None) -> LayerSchema:
        """geometry is the request boundary, forwarded to the provider.

        Providers that can only describe a layer by running the query need it
        (see `Provider.describe_schema`). The cache key includes it so a
        schema learned under one boundary is never served for another.
        """
        key = self._schema_key(layer_id, geometry)
        cached = self._schema_cache.get(key)
        if self._is_fresh(cached):
            return cached[0]
        layer = self.get_layer(layer_id)
        provider = self._providers.get(layer.provider)
        try:
            schema = provider.describe_schema(layer, geometry=geometry)
        except Exception as exc:
            return self._stale_or_error(cached, layer, layer_id, exc)
        self._schema_cache[key] = (schema, time.monotonic())
        return schema

    @staticmethod
    def _schema_key(layer_id: str, geometry) -> Tuple[str, Optional[bytes]]:
        return layer_id, None if geometry is None else geometry.wkb

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
