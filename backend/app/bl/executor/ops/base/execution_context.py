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
        geometry = self._geometry(push_down_geometry, geometry_hint)
        layer = self.catalog.get_layer(layer_id)
        provider_range, provider_filters = self._pushdowns(
            layer.provider, temporal_range, attribute_filters
        )
        cache_key = self._cache_key(layer_id, geometry, provider_range, provider_filters)
        if cache_key in self.feature_cache:
            return self.feature_cache[cache_key]
        provider = self.providers.get(layer.provider)
        options = self._provider_options(geometry, provider_range, provider_filters)
        gdf = provider.fetch_features(layer, **options)
        gdf.attrs["temporal_field"] = self.catalog.get_schema(layer_id).temporal_field
        self.feature_cache[cache_key] = gdf
        return gdf

    def _geometry(self, push_down: bool, hint):
        return self.user_geometry if hint is None and push_down else hint

    @staticmethod
    def _pushdowns(provider: str, temporal_range, attribute_filters):
        provider_range = temporal_range if provider in ("cubes", "tyche") else None
        provider_filters = attribute_filters if provider == "mqs" else None
        return provider_range, provider_filters

    def _provider_options(self, geometry, temporal_range, attribute_filters):
        options = {"now": self.now, "geometry": geometry}
        if temporal_range is not None:
            options["temporal_range"] = temporal_range
        if attribute_filters is not None:
            options["attribute_filters"] = attribute_filters
        return options

    def proximity_geometry(self, distance_m: float) -> Optional[BaseGeometry]:
        if self.user_geometry is None:
            return None
        return buffer_wgs84_geometry(self.user_geometry, distance_m)

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
