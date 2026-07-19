"""MQS provider orchestration.

Entity parsing, filter construction, pagination, spatial splitting, enrichment,
and schema inference are separated into focused collaborators.
"""

from datetime import datetime
from typing import List, Optional, Sequence, Tuple

import geopandas as gpd
import httpx
from shapely.geometry.base import BaseGeometry

from app.bl.ports.layer_meta import LayerMeta
from app.bl.ports.layer_schema import LayerSchema
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.providers.mqs_entity_mapper import MqsEntityMapper
from app.dal.providers.mqs_entity_stream import MqsEntityStream
from app.dal.providers.mqs_filter_builder import MqsFilterBuilder
from app.dal.providers.mqs_gateway import MqsGateway
from app.dal.providers.mqs_schema_builder import MqsSchemaBuilder
from app.dal.providers.mqs_source import MqsSource


class MqsProvider:
    _MAX_SAMPLE_CHARS = 40
    _METADATA_SAMPLE_SIZE = 10

    def __init__(
        self,
        settings_store: RuntimeSettingsStore,
        transport: Optional[httpx.BaseTransport] = None,
        detail_concurrency: int = 16,
    ) -> None:
        self._source = MqsSource()
        self._mapper = MqsEntityMapper()
        self._filters = MqsFilterBuilder()
        self._gateway = MqsGateway(
            settings_store, self._mapper, self._filters, transport
        )
        self._stream = MqsEntityStream(
            self._gateway, self._mapper, self._filters, detail_concurrency
        )
        self._schema = MqsSchemaBuilder(self._mapper, self._source)

    def describe_schema(self, layer: LayerMeta) -> LayerSchema:
        layer_id = self._source.layer_id(layer)
        with self._gateway.client() as client:
            entities = self._stream.enriched(client, layer_id, limit=20)
            return self._schema.build(layer, layer_id, entities)

    def fetch_features(
        self,
        layer: LayerMeta,
        now: Optional[datetime] = None,
        geometry: Optional[BaseGeometry] = None,
        limit: Optional[int] = None,
        attribute_filters: Optional[Sequence[Tuple[str, str]]] = None,
    ) -> gpd.GeoDataFrame:
        layer_id = self._source.layer_id(layer)
        with self._gateway.client() as client:
            entities = self._stream.enriched(
                client, layer_id, geometry, limit, attribute_filters
            )
            return self._mapper.to_gdf(layer_id, entities, geometry)

    def sample_for_metadata(
        self, layer: LayerMeta, limit: int = 100
    ) -> Tuple[gpd.GeoDataFrame, LayerSchema]:
        """Fetch one MQS sample and build its schema from the same entities.

        Metadata generation only displays ten entities. Stop as soon as ten
        valid rows with business properties are available instead of issuing
        another independent schema fetch and up to 120 EntityInfo calls.
        """
        layer_id = self._source.layer_id(layer)
        business_entities = []
        fallback_entities = []
        with self._gateway.client() as client:
            entities = self._stream.query(client, layer_id, limit=limit)
            for batch in self._stream.batched(
                entities, size=self._METADATA_SAMPLE_SIZE
            ):
                enriched = self._stream.enrich_batch(client, layer_id, batch)
                for entity in enriched:
                    if self._mapper.to_record(entity) is None:
                        continue
                    if len(fallback_entities) < self._METADATA_SAMPLE_SIZE:
                        fallback_entities.append(entity)
                    if self._mapper.property_attributes(entity):
                        business_entities.append(entity)
                if len(business_entities) >= self._METADATA_SAMPLE_SIZE:
                    break
        sampled = (
            business_entities[:self._METADATA_SAMPLE_SIZE]
            if business_entities else fallback_entities
        )
        return (
            self._mapper.to_gdf(layer_id, sampled),
            self._schema.build(layer, layer_id, sampled),
        )

    def sample_field_values(
        self, layer: LayerMeta, field: str, limit: int = 20
    ) -> List[str]:
        layer_id = self._source.layer_id(layer)
        values: List[str] = []
        sample_size = min(_PAGE_SIZE, max(limit * 5, 20))
        with self._gateway.client() as client:
            entities, _ = self._gateway.entities_page(
                client, layer_id, {"from": 0, "to": sample_size}
            )
            self._collect_samples(client, layer_id, entities, field, limit, values)
        return values[:limit]

    def list_remote_layers(self) -> List[dict]:
        return self._gateway.list_layers()

    def _collect_samples(
        self, client, layer_id: str, entities: List[dict], field: str,
        limit: int, values: List[str],
    ) -> None:
        for batch in self._stream.batched(entities):
            for entity in self._stream.enrich_batch(client, layer_id, batch):
                record = self._mapper.to_record(entity)
                value = record[1].get(field) if record is not None else None
                self._append_sample(values, value)
                if len(values) >= limit:
                    return

    def _append_sample(self, values: List[str], value: object) -> None:
        if value is None:
            return
        text = str(value)[:self._MAX_SAMPLE_CHARS]
        if text not in values:
            values.append(text)


_source_compat = MqsSource()
mqs_layer_id = _source_compat.layer_id
_PAGE_SIZE = MqsGateway.PAGE_SIZE
_MAX_FEATURES_PER_LAYER = MqsEntityStream.MAX_FEATURES_PER_LAYER
