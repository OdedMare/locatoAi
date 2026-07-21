"""Infer MQS business schema from enriched entity details."""

import logging
from typing import Dict, Iterable

from app.bl.catalog.models.layer_field import LayerField
from app.bl.catalog.models.layer_meta import LayerMeta
from app.bl.catalog.models.layer_schema import LayerSchema
from app.dal.providers.mqs.entity_mapper import MqsEntityMapper
from app.dal.providers.mqs.source import MqsSource


class MqsSchemaBuilder:
    _MAX_SAMPLE_CHARS = 40

    def __init__(self, mapper: MqsEntityMapper, source: MqsSource) -> None:
        self._mapper = mapper
        self._source = source
        self._logger = logging.getLogger(__name__)

    def build(
        self, layer: LayerMeta, layer_id: str, entities: Iterable[dict]
    ) -> LayerSchema:
        dynamic: Dict[str, LayerField] = {}
        for entity in entities:
            for name, value in self._mapper.property_attributes(entity).items():
                self._add_sample(dynamic, name, value)
        self._logger.info(
            "MQS schema layer=%s dynamic_fields=%d names=%s",
            layer_id, len(dynamic), list(dynamic),
        )
        return LayerSchema(
            layer_id=layer.id,
            geometry_type="Polygon",
            fields=list(self._mapper.FIXED_FIELDS) + list(dynamic.values()),
            temporal_field=self._source.temporal_field(layer),
        )

    def _add_sample(
        self, fields: Dict[str, LayerField], name: str, value: object
    ) -> None:
        sample = str(value)[:self._MAX_SAMPLE_CHARS]
        existing = fields.get(name)
        if existing is None:
            fields[name] = LayerField(
                name=name, type=self._field_type(value), samples=[sample]
            )
        elif sample not in existing.samples and len(existing.samples) < 5:
            existing.samples.append(sample)

    @staticmethod
    def _field_type(value: object) -> str:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return "number"
        return "string"
