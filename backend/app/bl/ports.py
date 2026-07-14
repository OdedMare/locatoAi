"""Ports (abstract interfaces) the business logic depends on.

DIP: the BL owns these contracts; the DAL implements them. Swapping
Postgres for another store, or the mock ArcGIS provider for a real one,
must not touch any BL module.
"""

from datetime import datetime
from typing import List, Optional, Protocol, Tuple

import geopandas as gpd
from pydantic import BaseModel


class LayerMeta(BaseModel):
    """One row of the catalog (public.layers). Metadata only — never features."""

    id: str
    name: str
    description: str = ""
    tags: List[str] = []
    provider: str
    source_url: str


class LayerField(BaseModel):
    name: str
    type: str
    description: str = ""
    samples: List[str] = []
    """A few distinct example values — lets the plan agent write
    attribute filters that match the data's language/format."""


class LayerSchema(BaseModel):
    """Schema of a layer as reported by its provider (fetched on demand)."""

    layer_id: str
    geometry_type: str
    fields: List[LayerField]
    temporal_field: Optional[str] = None
    """Name of the field holding this layer's event time, if any — set by
    the provider (v0.2: this used to be a hardcoded 'timestamp' column
    name in the executor; now each provider declares its own). None means
    the layer has no temporal dimension."""


class LayersRepository(Protocol):
    """Catalog store (implemented by dal.layers_repository)."""

    def list_layers(self) -> List[LayerMeta]: ...

    def get_layer(self, layer_id: str) -> Optional[LayerMeta]: ...

    def add_layer(self, layer: LayerMeta) -> LayerMeta: ...

    def upsert_layer(self, layer: LayerMeta) -> Tuple[LayerMeta, bool]:
        """Insert or update by (provider, source_url); returns (layer, created).
        Updates touch name/description only — tags may be LLM-enriched."""
        ...


class Provider(Protocol):
    """A GIS data provider (implemented by dal.providers.*).

    ISP: this is intentionally the whole surface — describe and fetch.
    """

    def describe_schema(self, layer: LayerMeta) -> LayerSchema: ...

    def fetch_features(
        self, layer: LayerMeta, now: Optional[datetime] = None
    ) -> gpd.GeoDataFrame: ...

    def sample_field_values(
        self, layer: LayerMeta, field: str, limit: int = 20
    ) -> List[str]:
        """Distinct example values of one field — backs the plan agent's
        on-demand sample_field tool. Values are untrusted text."""
        ...


class ProviderRegistry(Protocol):
    """Resolves a catalog `provider` name to a Provider instance."""

    def get(self, provider_name: str) -> Provider: ...


class LLMClient(Protocol):
    """JSON-mode LLM completion (implemented by dal.llm.*).

    Returns the parsed JSON object or raises common.errors.AgentError.
    """

    def complete_json(self, system: str, user: str) -> dict: ...

    def list_models(self) -> List[str]: ...
