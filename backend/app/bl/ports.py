"""Ports (abstract interfaces) the business logic depends on.

DIP: the BL owns these contracts; the DAL implements them. Swapping
Postgres for another store, or the mock ArcGIS provider for a real one,
must not touch any BL module.
"""

from datetime import datetime
from typing import List, Optional, Protocol

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


class LayerSchema(BaseModel):
    """Schema of a layer as reported by its provider (fetched on demand)."""

    layer_id: str
    geometry_type: str
    fields: List[LayerField]


class LayersRepository(Protocol):
    """Catalog store (implemented by dal.layers_repository)."""

    def list_layers(self) -> List[LayerMeta]: ...

    def get_layer(self, layer_id: str) -> Optional[LayerMeta]: ...


class Provider(Protocol):
    """A GIS data provider (implemented by dal.providers.*).

    ISP: this is intentionally the whole surface — describe and fetch.
    """

    def describe_schema(self, layer: LayerMeta) -> LayerSchema: ...

    def fetch_features(
        self, layer: LayerMeta, now: Optional[datetime] = None
    ) -> gpd.GeoDataFrame: ...


class ProviderRegistry(Protocol):
    """Resolves a catalog `provider` name to a Provider instance."""

    def get(self, provider_name: str) -> Provider: ...
