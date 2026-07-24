"""Cubes provider orchestration."""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

import geopandas as gpd
import httpx
from shapely.geometry.base import BaseGeometry

from app.bl.catalog.models.layer_meta import LayerMeta
from app.bl.catalog.models.layer_parameter import LayerParameter
from app.bl.catalog.models.layer_parameter_option import LayerParameterOption
from app.bl.catalog.models.layer_schema import LayerSchema
from app.dal.providers.flapi.client_factory import FlapiClientFactory
from app.dal.providers.flapi.cube_gateway import CubesGateway
from app.dal.providers.flapi.cube_metadata_gateway import CubesMetadataGateway
from app.dal.providers.flapi.cube_parameter_loader import CubesParameterLoader
from app.dal.providers.flapi.cube_query_builder import CubesQueryBuilder
from app.dal.providers.flapi.schema_mapper import FlapiSchemaMapper
from app.dal.providers.flapi.cube_source import CubesSource


class CubesProvider:
    _SCHEMA_SAMPLE_LIMIT = 100

    def __init__(self, clients: FlapiClientFactory) -> None:
        self._source = CubesSource()
        self._query = CubesQueryBuilder()
        self._mapper = FlapiSchemaMapper()
        self._clients = clients
        self._metadata = CubesMetadataGateway(
            self._clients, self._source, CubesParameterLoader()
        )
        self._gateway = CubesGateway(
            self._clients, self._source, self._query, self._mapper
        )
        self._schema_cache: Dict[Tuple[str, str], LayerSchema] = {}

    @property
    def _transport(self) -> Optional[httpx.BaseTransport]:
        return self._clients.transport

    @_transport.setter
    def _transport(self, transport: Optional[httpx.BaseTransport]) -> None:
        self._clients.set_transport(transport)

    def describe_schema(self, layer: LayerMeta) -> LayerSchema:
        metadata = self._metadata.metadata(layer)
        cache_key = self._schema_cache_key(layer)
        sampled = self._schema_cache.get(cache_key)
        if sampled is None:
            self.fetch_features(layer, limit=self._SCHEMA_SAMPLE_LIMIT)
            sampled = self._schema_cache.get(cache_key)
        return self._mapper.with_layer_roles(
            self._mapper.merge_schema(layer.id, metadata, sampled), layer
        )

    def list_dynamic_parameters(self, layer: LayerMeta) -> List[LayerParameter]:
        parameters = self._configured_parameters(layer)
        return [parameter for parameter in parameters if parameter.is_dynamic]

    def list_configurable_parameters(
        self, layer: LayerMeta, refresh: bool = False
    ) -> List[LayerParameter]:
        return [
            parameter for parameter in self._configured_parameters(layer, refresh)
            if self._query.requires_configuration(parameter)
        ]

    def requires_geometry(self, layer: LayerMeta) -> bool:
        return self._query.requires_geometry(
            self._configured_parameters(layer)
        )

    def fetch_features(
        self,
        layer: LayerMeta,
        now: Optional[datetime] = None,
        geometry: Optional[BaseGeometry] = None,
        limit: Optional[int] = None,
        temporal_range: Optional[Tuple[str, str]] = None,
        attribute_filters: Optional[List[Tuple[str, str]]] = None,
    ) -> gpd.GeoDataFrame:
        return self._fetch_features(
            layer, now, geometry, limit, temporal_range,
            allow_missing_geometry=False,
        )

    def sample_for_metadata(
        self, layer: LayerMeta, limit: int = 100,
        geometry: Optional[BaseGeometry] = None,
    ) -> Tuple[gpd.GeoDataFrame, LayerSchema]:
        """Sample a cube with an optional user-selected preview boundary.

        Cubes that declare a required polygon are held by the metadata
        generator until the UI supplies one. Cubes without that requirement
        can still be previewed without a boundary.
        """
        features = self._fetch_features(
            layer, geometry=geometry, limit=limit,
            allow_missing_geometry=geometry is None,
        )
        return features, self.describe_schema(layer)

    def _fetch_features(
        self,
        layer: LayerMeta,
        now: Optional[datetime] = None,
        geometry: Optional[BaseGeometry] = None,
        limit: Optional[int] = None,
        temporal_range: Optional[Tuple[str, str]] = None,
        allow_missing_geometry: bool = False,
    ) -> gpd.GeoDataFrame:
        metadata = self._metadata.metadata(layer)
        rows = self._gateway.fetch_rows(
            layer, self._configured_parameters(layer), geometry,
            self._mapper.results_limit(metadata), limit, now, temporal_range,
            self._source.query_mode(layer),
            allow_missing_geometry,
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
        return self._metadata.autocomplete(layer, parameter_name)

    def _configured_parameters(
        self, layer: LayerMeta, refresh: bool = False
    ) -> List[LayerParameter]:
        metadata = self._metadata.metadata(layer, refresh=refresh)
        parameters = self._mapper.metadata_parameters(metadata)
        return self._query.resolve_parameters(
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
PARAMETER_PREFIX = CubesSource.PARAMETER_PREFIX
