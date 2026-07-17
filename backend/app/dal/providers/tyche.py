"""Tyche provider orchestration.

Request construction, transport, feature mapping, and schema inference live in
focused collaborators. This class only implements the provider use cases.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

import geopandas as gpd
import httpx
from shapely.geometry.base import BaseGeometry

from app.bl.ports.layer_meta import LayerMeta
from app.bl.ports.layer_schema import LayerSchema
from app.common.errors.provider_error import ProviderError
from app.common.geo import empty_features_gdf
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.providers.tyche_feature_mapper import TycheFeatureMapper
from app.dal.providers.tyche_gateway import TycheGateway
from app.dal.providers.tyche_query_builder import TycheQueryBuilder
from app.dal.providers.tyche_schema_builder import TycheSchemaBuilder


class TycheProvider:
    _SOURCE_URL = "tyche://ourforces"
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
        self._validate_source(layer)
        return self._schema_builder.build(layer, self._samples.get(layer.id, []))

    def fetch_features(
        self,
        layer: LayerMeta,
        now: Optional[datetime] = None,
        geometry: Optional[BaseGeometry] = None,
        limit: Optional[int] = None,
        temporal_range: Optional[Tuple[str, str]] = None,
    ) -> gpd.GeoDataFrame:
        self._validate_source(layer)
        if limit is not None and limit < 1:
            return empty_features_gdf()
        rows = self._fetch_rows(now, geometry, limit, temporal_range)
        self._samples[layer.id] = rows[:100]
        return self._features_in_boundary(rows, geometry)

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
        now: Optional[datetime],
        geometry: Optional[BaseGeometry],
        limit: Optional[int],
        temporal_range: Optional[Tuple[str, str]],
    ) -> List[dict]:
        return self._gateway.fetch(
            lambda size, tracker: self._query_builder.build(
                now, geometry, temporal_range, size, tracker
            ),
            limit,
        )

    def _features_in_boundary(
        self, rows: List[dict], geometry: Optional[BaseGeometry]
    ) -> gpd.GeoDataFrame:
        features = self._mapper.to_gdf(rows)
        if geometry is not None and not features.empty:
            features = features[features.geometry.intersects(geometry)]
        return features.reset_index(drop=True)

    def _validate_source(self, layer: LayerMeta) -> None:
        if layer.source_url.strip().rstrip("/").lower() != self._SOURCE_URL:
            raise ProviderError("Tyche supports only source_url=tyche://ourforces")
