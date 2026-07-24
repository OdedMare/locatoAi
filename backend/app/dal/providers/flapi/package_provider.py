"""Flow Package provider orchestration."""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

from app.bl.catalog.models.layer_meta import LayerMeta
from app.bl.catalog.models.layer_parameter import LayerParameter
from app.bl.catalog.models.layer_schema import LayerSchema
from app.dal.providers.flapi.schema_mapper import FlapiSchemaMapper
from app.dal.providers.flapi.package_gateway import FlowPackageGateway
from app.dal.providers.flapi.package_metadata import FlowPackageMetadata
from app.dal.providers.flapi.package_serializer import FlowPackageSerializer
from app.dal.providers.flapi.source import FlapiSource


class FlowPackageProvider:
    _SAMPLE_LIMIT = 100

    def __init__(self, clients) -> None:
        self._source = FlapiSource()
        self._metadata = FlowPackageMetadata()
        self._rows = FlapiSchemaMapper()
        self._gateway = FlowPackageGateway(clients, self._source, self._rows)
        self._serializer = FlowPackageSerializer(self._metadata)
        self._definitions: Dict[str, List[dict]] = {}
        self._schemas: Dict[Tuple[str, str], LayerSchema] = {}

    def describe_schema(self, layer: LayerMeta) -> LayerSchema:
        key = self._schema_key(layer)
        if key not in self._schemas:
            self.fetch_features(layer, limit=self._SAMPLE_LIMIT)
        return self._schemas[key]

    def list_configurable_parameters(
        self, layer: LayerMeta, refresh: bool = False
    ) -> List[LayerParameter]:
        definitions = self._parameter_definitions(layer, refresh)
        parameters = self._metadata.parameters(
            definitions, self._source.package_inputs(layer)
        )
        return [
            item.model_copy(update={"resolved_value": {"geometry": "boundary"}})
            if self._definition_for(definitions, item.name) is not None
            and self._metadata.is_geometry(
                self._definition_for(definitions, item.name)
            )
            else item
            for item in parameters
        ]

    def requires_geometry(self, layer: LayerMeta) -> bool:
        inputs = self._source.package_inputs(layer)
        return any(
            self._required(item)
            and self._metadata.is_geometry(item)
            and self._name(item) not in inputs
            and self._metadata.value(item, "Value", "value") in (None, "")
            for item in self._parameter_definitions(layer)
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
        definitions = self._parameter_definitions(layer)
        body = self._serializer.build(
            definitions, self._source.package_inputs(layer),
            geometry, temporal_range,
        )
        rows = self._gateway.execute(layer, body)
        schema = self._schema(layer, rows, definitions)
        self._schemas[self._schema_key(layer)] = schema
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

    def _parameter_definitions(
        self, layer: LayerMeta, refresh: bool = False
    ) -> List[dict]:
        package_id = self._source.package_id(layer)
        if refresh or package_id not in self._definitions:
            payload = self._gateway.definitions(layer)
            self._definitions[package_id] = self._metadata.definitions(payload)
        return self._definitions[package_id]

    def _schema(
        self, layer: LayerMeta, rows: List[dict], definitions: List[dict]
    ) -> LayerSchema:
        inferred = self._rows.infer_schema(layer.id, rows)
        schema = inferred.model_copy(update={
            "parameters": self._metadata.parameters(
                definitions, self._source.package_inputs(layer)
            ),
            "source_name": f"Flow Package {self._source.package_id(layer)}",
        })
        return self._rows.with_layer_roles(schema, layer)

    @staticmethod
    def _schema_key(layer: LayerMeta) -> Tuple[str, str]:
        return layer.id, layer.source_url

    def _definition_for(
        self, definitions: List[dict], name: str
    ) -> Optional[dict]:
        return next(
            (item for item in definitions if self._name(item) == name), None
        )

    def _name(self, item: dict) -> str:
        return str(self._metadata.value(item, "Name", "name"))

    def _required(self, item: dict) -> bool:
        return self._metadata.bool_value(
            item, False, "IsRequired", "isRequired"
        )
