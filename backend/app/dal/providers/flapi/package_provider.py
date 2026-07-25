"""Flow Package provider orchestration."""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

from app.bl.catalog.models.layer_meta import LayerMeta
from app.bl.catalog.models.layer_schema import LayerSchema
from app.dal.providers.flapi.schema_mapper import FlapiSchemaMapper
from app.dal.providers.flapi.package_gateway import FlowPackageGateway
from app.dal.providers.flapi.package_serializer import FlowPackageSerializer
from app.dal.providers.flapi.source import FlapiSource


class FlowPackageProvider:
    """Runs catalog Flow Package layers through flunks.

    The schema is inferred from the rows a run returns — packages expose no
    separate discovery call through flunks, so describing a layer means running
    it once and caching the result.
    """

    _SAMPLE_LIMIT = 100

    def __init__(self, clients) -> None:
        self._source = FlapiSource()
        self._rows = FlapiSchemaMapper()
        self._gateway = FlowPackageGateway(clients, self._source, self._rows)
        self._serializer = FlowPackageSerializer()
        self._schemas: Dict[Tuple[str, str], LayerSchema] = {}

    def describe_schema(self, layer: LayerMeta) -> LayerSchema:
        key = self._schema_key(layer)
        if key not in self._schemas:
            self.fetch_features(layer, limit=self._SAMPLE_LIMIT)
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
        input_cube = self._serializer.build_input_cube(
            self._source.package_input_cube_name(layer),
            self._source.package_input_cube_parameter(layer),
            kind=self._source.package_input_cube_kind(layer),
            temporal_range=temporal_range,
            geometry=geometry,
            now=now,
        )
        rows = self._gateway.execute(
            layer, input_cube, self._source.package_output_cube_name(layer),
        )
        self._schemas[self._schema_key(layer)] = self._schema(layer, rows)
        features = self._rows.to_gdf(rows)
        if geometry is not None and not features.empty:
            features = features[features.geometry.intersects(geometry)]
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
