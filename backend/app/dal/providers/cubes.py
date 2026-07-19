"""Cubes provider orchestration."""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

import geopandas as gpd
import httpx
from shapely.geometry.base import BaseGeometry

from app.bl.ports.layer_meta import LayerMeta
from app.bl.ports.layer_parameter import LayerParameter
from app.bl.ports.layer_parameter_option import LayerParameterOption
from app.bl.ports.layer_schema import LayerSchema
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.providers.cubes_gateway import CubesGateway
from app.dal.providers.cubes_query_builder import CubesQueryBuilder
from app.dal.providers.cubes_schema_mapper import CubesSchemaMapper
from app.dal.providers.cubes_source import CubesSource


class CubesProvider:
    _SCHEMA_SAMPLE_LIMIT = 100

    def __init__(
        self,
        settings_store: RuntimeSettingsStore,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self._source = CubesSource()
        self._query = CubesQueryBuilder()
        self._mapper = CubesSchemaMapper()
        self._gateway = CubesGateway(
            settings_store, self._source, self._query, self._mapper, transport
        )
        self._schema_cache: Dict[Tuple[str, str], LayerSchema] = {}

    @property
    def _transport(self) -> Optional[httpx.BaseTransport]:
        return self._gateway._transport

    @_transport.setter
    def _transport(self, transport: Optional[httpx.BaseTransport]) -> None:
        self._gateway.set_transport(transport)

    def describe_schema(self, layer: LayerMeta) -> LayerSchema:
        metadata = self._gateway.metadata(layer)
        cache_key = self._schema_cache_key(layer)
        sampled = self._schema_cache.get(cache_key)
        if sampled is None:
            self.fetch_features(layer, limit=self._SCHEMA_SAMPLE_LIMIT)
            sampled = self._schema_cache.get(cache_key)
        return self._mapper.merge_schema(layer.id, metadata, sampled)

    def list_dynamic_parameters(self, layer: LayerMeta) -> List[LayerParameter]:
        parameters = self._configured_parameters(layer)
        return [parameter for parameter in parameters if parameter.is_dynamic]

    def fetch_features(
        self,
        layer: LayerMeta,
        now: Optional[datetime] = None,
        geometry: Optional[BaseGeometry] = None,
        limit: Optional[int] = None,
        temporal_range: Optional[Tuple[str, str]] = None,
    ) -> gpd.GeoDataFrame:
        metadata = self._gateway.metadata(layer)
        rows = self._gateway.fetch_rows(
            layer, self._configured_parameters(layer), geometry,
            self._mapper.results_limit(metadata), limit, now, temporal_range,
            self._source.query_mode(layer),
        )
        self._schema_cache[self._schema_cache_key(layer)] = self._mapper.infer_schema(
            layer.id, rows
        )
        return self._features(rows, geometry, limit)

    def sample_field_values(
        self, layer: LayerMeta, field: str, limit: int = 20
    ) -> List[str]:
        features = self.fetch_features(layer, limit=max(limit * 5, 20))
        if field not in features.columns:
            return []
        values = [str(value)[:80] for value in features[field].dropna()]
        return list(dict.fromkeys(values))[:limit]

    def fetch_autocomplete_options(
        self, layer: LayerMeta, parameter_name: str
    ) -> List[LayerParameterOption]:
        return self._gateway.autocomplete(layer, parameter_name)

    def _configured_parameters(self, layer: LayerMeta) -> List[LayerParameter]:
        metadata = self._gateway.metadata(layer)
        parameters = self._mapper.metadata_parameters(metadata)
        return self._query.resolve_dynamic(
            parameters, self._source.resolved_parameters(layer)
        )

    @staticmethod
    def _schema_cache_key(layer: LayerMeta) -> Tuple[str, str]:
        return layer.id, layer.source_url

    def _features(
        self, rows: List[dict], geometry: Optional[BaseGeometry], limit: Optional[int]
    ) -> gpd.GeoDataFrame:
        features = self._mapper.to_gdf(rows)
        if geometry is not None:
            features = features[features.geometry.intersects(geometry)]
        return features.iloc[:limit] if limit is not None else features


_source_compat = CubesSource()
cubes_database_name = _source_compat.database_name
cubes_query_mode = _source_compat.query_mode
cubes_resolved_parameters = _source_compat.resolved_parameters
DYNAMIC_PARAM_PREFIX = CubesSource.DYNAMIC_PARAM_PREFIX
