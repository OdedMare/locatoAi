"""Op interface + registry.

OCP: adding op #7 means adding one module with @register_op — the engine
never changes. Each op handler does exactly one spatial operation (SRP).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

from app.bl.catalog.catalog_service import CatalogService
from app.bl.plan.models import Step
from app.bl.ports import ProviderRegistry


@dataclass
class ExecutionContext:
    """Everything ops may need. Engine-owned, passed to every op."""

    catalog: CatalogService
    providers: ProviderRegistry
    user_geometry: BaseGeometry | None
    now: datetime
    results: dict[str, gpd.GeoDataFrame] = field(default_factory=dict)

    def load_layer_features(self, layer_id: str) -> gpd.GeoDataFrame:
        """Shared by `load` and `near` (which loads its target layer)."""
        layer = self.catalog.get_layer(layer_id)
        provider = self.providers.get(layer.provider)
        return provider.fetch_features(layer, now=self.now)


class OpHandler(ABC):
    """One handler per plan op."""

    @abstractmethod
    def run(self, step: Step, ctx: ExecutionContext) -> gpd.GeoDataFrame: ...


_REGISTRY: dict[str, OpHandler] = {}


def register_op(op_name: str) -> Callable[[type[OpHandler]], type[OpHandler]]:
    def decorator(cls: type[OpHandler]) -> type[OpHandler]:
        _REGISTRY[op_name] = cls()
        return cls

    return decorator


def get_op_handler(op_name: str) -> OpHandler:
    handler = _REGISTRY.get(op_name)
    if handler is None:
        raise KeyError(f"No handler registered for op '{op_name}'")
    return handler
