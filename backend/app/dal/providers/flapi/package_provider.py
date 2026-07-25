"""Flow Package provider orchestration."""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

from app.bl.catalog.models.layer_meta import LayerMeta
from app.bl.catalog.models.layer_schema import LayerSchema
from app.dal.providers.flapi.schema_mapper import FlapiSchemaMapper
from app.dal.providers.flapi.package_debug import FlowPackageDebug
from app.dal.providers.flapi.package_gateway import FlowPackageGateway
from app.dal.providers.flapi.package_serializer import FlowPackageSerializer
from app.dal.providers.flapi.source import FlapiSource


class FlowPackageProvider:
    """Runs catalog Flow Package layers through flunks.

    The schema is inferred from the rows a run returns — packages expose no
    separate discovery call through flunks, so describing a layer means running
    it once and caching the result.
    """

    def __init__(self, clients) -> None:
        self._source = FlapiSource()
        self._rows = FlapiSchemaMapper()
        self._gateway = FlowPackageGateway(clients, self._source, self._rows)
        self._serializer = FlowPackageSerializer()
        self._schemas: Dict[Tuple[str, str], LayerSchema] = {}
        self._logger = logging.getLogger(__name__)

    def describe_schema(
        self, layer: LayerMeta, geometry: Optional[BaseGeometry] = None
    ) -> LayerSchema:
        key = self._schema_key(layer)
        self._logger.info(
            "FLAPI describe_schema layer=%s cached=%s %s",
            layer.id, key in self._schemas,
            FlowPackageDebug.geometry(geometry),
        )
        if key not in self._schemas:
            # A package has no discovery call: describing it means running it,
            # and a geographic package rejects an empty input, so the request
            # boundary is required rather than optional here. No limit: the run
            # returns every row the package produced.
            self.fetch_features(layer, geometry=geometry)
        return self._schemas[key]

    def fetch_features(
        self,
        layer: LayerMeta,
        now: Optional[datetime] = None,
        geometry: Optional[BaseGeometry] = None,
        limit: Optional[int] = None,
        temporal_range: Optional[Tuple[str, str]] = None,
        attribute_filters: Optional[List[Tuple[str, str]]] = None,
    ) -> gpd.GeoDataFrame:
        kind = self._source.package_input_cube_kind(layer)
        self._logger.info(
            "FLAPI fetch_features layer=%s package=%s kind=%s limit=%s "
            "temporal_range=%s %s",
            layer.id, self._source.package_id(layer), kind, limit,
            temporal_range, FlowPackageDebug.geometry(geometry),
        )
        # The parsed source_url: a mistyped cube name here is indistinguishable
        # from a package-side error in FLAPI's own message.
        self._logger.info(
            "FLAPI source layer=%s input_cube=%r parameter=%r output_cube=%r "
            "source_url=%s",
            layer.id, self._source.package_input_cube_name(layer),
            self._source.package_input_cube_parameter(layer),
            self._source.package_output_cube_name(layer), layer.source_url,
        )
        input_cube = self._serializer.build_input_cube(
            self._source.package_input_cube_name(layer),
            self._source.package_input_cube_parameter(layer),
            kind=kind,
            temporal_range=temporal_range,
            geometry=geometry,
            now=now,
        )
        rows = self._gateway.execute(
            layer, input_cube, self._source.package_output_cube_name(layer),
        )
        self._schemas[self._schema_key(layer)] = self._schema(layer, rows)
        features = self._rows.to_gdf(rows)
        mapped = len(features)
        if geometry is not None and not features.empty:
            features = features[features.geometry.intersects(geometry)]
        # Rows can vanish here rather than at the provider: a package that
        # ignored the boundary, or geometry text the mapper could not parse.
        self._logger.info(
            "FLAPI fetch_features layer=%s rows=%d mapped=%d "
            "after_intersect=%d returned=%d",
            layer.id, len(rows), mapped, len(features),
            min(len(features), limit) if limit is not None else len(features),
        )
        if limit is not None:
            features = features.iloc[:limit]
        return features.reset_index(drop=True)

    def sample_for_metadata(
        self, layer: LayerMeta, limit: int = 100,
        geometry: Optional[BaseGeometry] = None,
    ):
        features = self.fetch_features(layer, geometry=geometry, limit=limit)
        return features, self._schemas[self._schema_key(layer)]

    def sample_field_values(
        self, layer: LayerMeta, field: str, limit: int = 20
    ) -> List[str]:
        features = self.fetch_features(layer, limit=max(limit * 5, 20))
        if field not in features.columns:
            return []
        values = [str(value)[:80] for value in features[field].dropna()]
        return list(dict.fromkeys(values))[:limit]

    def _schema(self, layer: LayerMeta, rows: List[dict]) -> LayerSchema:
        inferred = self._rows.infer_schema(layer.id, rows)
        schema = inferred.model_copy(update={
            "source_name": f"Flow Package {self._source.package_id(layer)}",
        })
        return self._rows.with_layer_roles(schema, layer)

    @staticmethod
    def _schema_key(layer: LayerMeta) -> Tuple[str, str]:
        return layer.id, layer.source_url
