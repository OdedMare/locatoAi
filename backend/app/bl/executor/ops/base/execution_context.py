from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

from app.bl.catalog.catalog_service import CatalogService
from app.bl.ports.provider_registry import ProviderRegistry
from app.common.geo import buffer_wgs84_geometry


@dataclass
class ExecutionContext:
    """Everything ops may need. Engine-owned, passed to every op."""

    catalog: CatalogService
    providers: ProviderRegistry
    user_geometry: Optional[BaseGeometry]
    now: datetime
    results: Dict[str, gpd.GeoDataFrame] = field(default_factory=dict)
    feature_cache: Dict[str, gpd.GeoDataFrame] = field(default_factory=dict)
    load_temporal_ranges: Dict[str, Tuple[str, str]] = field(default_factory=dict)
    load_attribute_filters: Dict[str, List[Tuple[str, str]]] = field(default_factory=dict)

    def load_layer_features(
        self, layer_id: str, push_down_geometry: bool = True,
        geometry_hint: Optional[BaseGeometry] = None,
        temporal_range: Optional[Tuple[str, str]] = None,
        attribute_filters: Optional[List[Tuple[str, str]]] = None,
    ) -> gpd.GeoDataFrame:
        """Shared by `load` and `near` (which loads its target layer).

        Every layer is scoped to the request's user_geometry by default. A
        caller may instead provide geometry_hint; bounded proximity operations
        use the request geometry expanded by their maximum distance. Explicitly
        disabling pushdown is reserved for non-query/internal callers.

        Stashes the layer's temporal_field (from its provider-reported
        schema) on the GeoDataFrame's .attrs — pandas/GeoPandas .attrs
        survive boolean-mask filtering, so any op downstream in the same
        chain (e.g. temporal_filter) can read it without a hardcoded
        column name. See ops/temporal_filter.py.
        """
        geometry = geometry_hint
        if geometry is None and push_down_geometry:
            geometry = self.user_geometry
        layer = self.catalog.get_layer(layer_id)
        provider_range = (
            temporal_range if layer.provider in ("cubes", "tyche") else None
        )
        provider_filters = (
            attribute_filters if layer.provider == "mqs" else None
        )
        cache_key = self._cache_key(layer_id, geometry, provider_range, provider_filters)
        if cache_key in self.feature_cache:
            return self.feature_cache[cache_key]
        provider = self.providers.get(layer.provider)
        options = {"now": self.now, "geometry": geometry}
        if provider_range is not None:
            options["temporal_range"] = provider_range
        if provider_filters is not None:
            options["attribute_filters"] = provider_filters
        gdf = provider.fetch_features(layer, **options)
        gdf.attrs["temporal_field"] = self.catalog.get_schema(layer_id).temporal_field
        self.feature_cache[cache_key] = gdf
        return gdf

    @staticmethod
    def _cache_key(
        layer_id: str, geometry: Optional[BaseGeometry],
        temporal_range: Optional[Tuple[str, str]],
        attribute_filters: Optional[List[Tuple[str, str]]] = None,
    ) -> str:
        geometry_key = geometry.wkb_hex if geometry is not None else "unbounded"
        time_key = ":".join(temporal_range) if temporal_range is not None else "all-time"
        filters_key = (
            ";".join(f"{field}={value}" for field, value in sorted(attribute_filters))
            if attribute_filters else "no-filters"
        )
        return f"{layer_id}:{geometry_key}:{time_key}:{filters_key}"

    def proximity_geometry(self, distance_m: float) -> Optional[BaseGeometry]:
        if self.user_geometry is None:
            return None
        return buffer_wgs84_geometry(self.user_geometry, distance_m)
