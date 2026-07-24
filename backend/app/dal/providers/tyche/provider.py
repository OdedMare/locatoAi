"""Tyche provider orchestration.

Request construction, transport, feature mapping, and schema inference live in
focused collaborators. This class only implements the provider use cases.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

import geopandas as gpd
import httpx
from shapely.geometry.base import BaseGeometry

from app.bl.catalog.models.layer_meta import LayerMeta
from app.bl.catalog.models.layer_schema import LayerSchema
from app.bl.providers.provider import TEMPORAL_PUSHDOWN
from app.common.utils.geo_utils import empty_features_gdf
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.providers.tyche.feature_mapper import TycheFeatureMapper
from app.dal.providers.tyche.gateway import TycheGateway
from app.dal.providers.tyche.query_builder import TycheQueryBuilder
from app.dal.providers.tyche.schema_builder import TycheSchemaBuilder
from app.dal.providers.tyche.source import TycheSource


class TycheProvider:
    capabilities = frozenset({TEMPORAL_PUSHDOWN})
    _MAX_SAMPLE_CHARS = 80

    def __init__(
        self,
        settings_store: RuntimeSettingsStore,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self._mapper = TycheFeatureMapper()
        self._query_builder = TycheQueryBuilder()
        self._schema_builder = TycheSchemaBuilder()
        self._gateway = TycheGateway(settings_store, self._mapper, transport)
        self._samples: Dict[str, List[dict]] = {}

    def describe_schema(self, layer: LayerMeta) -> LayerSchema:
        source = TycheSource.parse(layer.source_url)
        rows = self._samples.get(layer.id)
        if rows is None and not source.is_our_forces:
            rows = self._fetch_rows(source, None, None, 100, None)
            self._samples[layer.id] = rows
        schema = self._schema_builder.build(
            layer, rows or [], source.time_field, source.geometry_field,
            layer.entity_field or source.entity_field, source.is_our_forces,
        )
        return schema.model_copy(update={"display_field": layer.display_field})

    def fetch_features(
        self,
        layer: LayerMeta,
        now: Optional[datetime] = None,
        geometry: Optional[BaseGeometry] = None,
        limit: Optional[int] = None,
        temporal_range: Optional[Tuple[str, str]] = None,
        attribute_filters: Optional[List[Tuple[str, str]]] = None,
    ) -> gpd.GeoDataFrame:
        source = TycheSource.parse(layer.source_url)
        if limit is not None and limit < 1:
            return empty_features_gdf()
        rows = self._fetch_rows(
            source, now, geometry, limit, temporal_range
        )
        self._samples[layer.id] = rows[:100]
        return self._features_in_boundary(
            rows, geometry, source.geometry_field
        )

    def sample_field_values(
        self, layer: LayerMeta, field: str, limit: int = 20,
    ) -> List[str]:
        features = self.fetch_features(layer, limit=max(limit * 5, 20))
        if field not in features.columns:
            return []
        values = [str(value)[:self._MAX_SAMPLE_CHARS]
                  for value in features[field].dropna()]
        return list(dict.fromkeys(values))[:limit]

    def _fetch_rows(
        self,
        source: TycheSource,
        now: Optional[datetime],
        geometry: Optional[BaseGeometry],
        limit: Optional[int],
        temporal_range: Optional[Tuple[str, str]],
    ) -> List[dict]:
        return self._gateway.fetch(
            source.route,
            lambda size, tracker: self._query_builder.build(
                now, geometry, temporal_range, size, tracker,
                source.time_field, source.geo_query_field,
            ),
            limit,
        )

    def _features_in_boundary(
        self, rows: List[dict], geometry: Optional[BaseGeometry],
        geometry_field: str,
    ) -> gpd.GeoDataFrame:
        features = self._mapper.to_gdf(rows, geometry_field)
        if geometry is not None and not features.empty:
            features = features[features.geometry.intersects(geometry)]
        return features.reset_index(drop=True)
