"""Render selected layer schemas for the plan-building prompt."""

import json
import logging


class LayerPromptFormatter:
    _DIET_SAMPLE_CHARS = 24

    def __init__(self, catalog) -> None:
        self._catalog = catalog
        self._logger = logging.getLogger(__name__)

    def format(self, layers, diet: bool = False) -> str:
        lines = []
        for layer in layers:
            schema = self._catalog.get_schema(layer.id)
            self._log_schema(layer.id, schema)
            lines.append(self._layer_line(layer, schema, diet))
            if schema.parameters:
                lines.append(self._parameters(schema))
        return "\n".join(lines)

    def _layer_line(self, layer, schema, diet: bool) -> str:
        return "- id: {id} | provider: {provider} | name: {name} | geometry: {geom}\n  fields: {fields}".format(
            id=layer.id, provider=layer.provider, name=layer.name,
            geom=schema.geometry_type,
            fields=self._fields(schema, diet),
        )

    def _fields(self, schema, diet: bool) -> str:
        if not schema.fields:
            return "(unknown)"
        return "; ".join(self._field(field, diet) for field in schema.fields)

    def _field(self, field, diet: bool) -> str:
        text = field.name + ":" + field.type if diet else (
            field.name + " (" + field.type + ")"
        )
        if not field.samples:
            return text
        samples = field.samples[:2] if diet else field.samples[:5]
        if diet:
            samples = [str(value)[:self._DIET_SAMPLE_CHARS] for value in samples]
            return text + "=" + json.dumps(samples, ensure_ascii=False)
        return text + " samples: " + json.dumps(samples, ensure_ascii=False)

    @staticmethod
    def _parameters(schema) -> str:
        values = (
            parameter.name + (" required" if parameter.required else " optional")
            for parameter in schema.parameters
        )
        return "  provider parameters: " + "; ".join(values)

    def _log_schema(self, layer_id, schema) -> None:
        self._logger.info(
            "Plan schema layer=%s fields=%d samples=%s",
            layer_id, len(schema.fields),
            {field.name: len(field.samples) for field in schema.fields},
        )
