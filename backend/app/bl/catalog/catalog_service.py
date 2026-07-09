"""Catalog service: layer lookup + on-demand schema fetching with TTL cache.

SRP: this module resolves layers and schemas. It does not execute plans,
talk HTTP, or know Postgres — the repository/provider ports do the I/O.
"""

import time

from app.bl.ports import (
    LayerMeta,
    LayerSchema,
    LayersRepository,
    ProviderRegistry,
)
from app.common.errors import LayerNotFoundError, ProviderError


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
        self._schema_cache: dict[str, tuple[LayerSchema, float]] = {}

    def list_layers(self) -> list[LayerMeta]:
        """All layers the agent may choose from (metadata only)."""
        return self._repository.list_layers()

    def get_layer(self, layer_id: str) -> LayerMeta:
        layer = self._repository.get_layer(layer_id)
        if layer is None:
            raise LayerNotFoundError(layer_id)
        return layer

    def get_schema(self, layer_id: str) -> LayerSchema:
        """Fetch a layer schema from its provider, cached with TTL.

        Providers may be slow or down — a stale cached schema is returned
        rather than failing, per the MVP guide.
        """
        cached = self._schema_cache.get(layer_id)
        if cached is not None and time.monotonic() - cached[1] < self._schema_ttl:
            return cached[0]

        layer = self.get_layer(layer_id)
        provider = self._providers.get(layer.provider)
        try:
            schema = provider.describe_schema(layer)
        except Exception as exc:
            if cached is not None:  # stale beats failed
                return cached[0]
            raise ProviderError(
                f"Provider '{layer.provider}' failed to describe layer {layer_id}"
            ) from exc

        self._schema_cache[layer_id] = (schema, time.monotonic())
        return schema
