"""Op interface + registry.

OCP: adding op #7 means adding one module with @register_op — the engine
never changes. Each op handler does exactly one spatial operation (SRP).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, Optional, Type, Union

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

from app.bl.catalog.catalog_service import CatalogService
from app.bl.plan.models.step import Step
from app.bl.ports.provider_registry import ProviderRegistry


@dataclass
class ExecutionContext:
    """Everything ops may need. Engine-owned, passed to every op."""

    catalog: CatalogService
    providers: ProviderRegistry
    user_geometry: Optional[BaseGeometry]
    now: datetime
    results: Dict[str, gpd.GeoDataFrame] = field(default_factory=dict)

    def load_layer_features(
        self, layer_id: str, push_down_geometry: bool = False
    ) -> gpd.GeoDataFrame:
        """Shared by `load` and `near` (which loads its target layer).

        push_down_geometry=True passes the request's user_geometry (when
        present) to the provider as an optional spatial-filter hint — see
        Provider.fetch_features. `near`'s target layer does NOT pass this:
        a target outside the viewport can still be the nearest one to an
        in-viewport feature, so it must stay unscoped.

        Stashes the layer's temporal_field (from its provider-reported
        schema) on the GeoDataFrame's .attrs — pandas/GeoPandas .attrs
        survive boolean-mask filtering, so any op downstream in the same
        chain (e.g. temporal_filter) can read it without a hardcoded
        column name. See ops/temporal_filter.py.
        """
        layer = self.catalog.get_layer(layer_id)
        provider = self.providers.get(layer.provider)
        geometry = self.user_geometry if push_down_geometry else None
        gdf = provider.fetch_features(layer, now=self.now, geometry=geometry)
        gdf.attrs["temporal_field"] = self.catalog.get_schema(layer_id).temporal_field
        return gdf


class OpHandler(ABC):
    """One handler per plan op."""

    @abstractmethod
    def run(self, step: Step, ctx: ExecutionContext) -> Union[gpd.GeoDataFrame, int]:
        """A GeoDataFrame for every op except a terminal `count` step,
        which returns a plain int (see engine.py and ops/count.py)."""
        ...


_REGISTRY: Dict[str, OpHandler] = {}


def register_op(op_name: str) -> Callable[[Type[OpHandler]], Type[OpHandler]]:
    def decorator(cls: Type[OpHandler]) -> Type[OpHandler]:
        _REGISTRY[op_name] = cls()
        return cls

    return decorator


def get_op_handler(op_name: str) -> OpHandler:
    handler = _REGISTRY.get(op_name)
    if handler is None:
        raise KeyError(f"No handler registered for op '{op_name}'")
    return handler
