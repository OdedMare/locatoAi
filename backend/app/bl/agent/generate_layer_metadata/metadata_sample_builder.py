"""Build a bounded metadata-generation prompt payload."""

import json

from app.common.errors.provider_error import ProviderError


class MetadataSampleBuilder:
    _SAMPLE_SIZE = 10
    _MAX_FIELDS = 20
    _MAX_VALUE_CHARS = 200
    _MAX_NAME_CHARS = 60

    def build(self, layer, features, schema):
        fields = [field for field in schema.fields if field.metadata_relevant]
        if layer.provider == "mqs" and not fields:
            raise ProviderError(
                "MQS property_list fields were not found in the EntityInfo response. "
                "Check the MQS User_ID setting and EntityInfo access for this layer"
            )
        sample_count = min(self._SAMPLE_SIZE, len(features))
        records = self._records(features, fields, sample_count)
        payload = self._payload(layer, schema, fields, records)
        return json.dumps(payload, ensure_ascii=False), sample_count

    def _records(self, features, fields, sample_count):
        field_names = {field.name for field in fields}
        sampled = features.sample(n=sample_count)
        raw_records = sampled.drop(columns=["geometry"], errors="ignore").to_dict("records")
        return [self._record(record, field_names) for record in raw_records]

    def _record(self, record, field_names) -> dict:
        business = [item for item in record.items() if item[0] in field_names]
        return {
            str(key)[:self._MAX_NAME_CHARS]: str(value)[:self._MAX_VALUE_CHARS]
            for key, value in business[:self._MAX_FIELDS]
        }

    def _payload(self, layer, schema, fields, records) -> dict:
        return {
            "layer_name": layer.name,
            "source_name": schema.source_name,
            "source_description": schema.source_description,
            "geometry_type": schema.geometry_type,
            "fields": [self._field(field) for field in fields[:self._MAX_FIELDS]],
            "parameters": [item.model_dump()
                           for item in schema.parameters[:self._MAX_FIELDS]],
            "random_entity_sample": records,
        }

    @staticmethod
    def _field(field) -> dict:
        return {
            "name": field.name, "type": field.type,
            "description": field.description,
        }
