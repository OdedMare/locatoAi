"""Build Tyche schemas from declared fields and recent samples."""

from typing import List

from app.bl.ports.layer_field import LayerField
from app.bl.ports.layer_meta import LayerMeta
from app.bl.ports.layer_schema import LayerSchema


class TycheSchemaBuilder:
    _MAX_SAMPLE_CHARS = 80
    _FIELDS = (
        ("eventTime", "date", "Event occurrence time"),
        ("arriveTime", "date", "Time the event arrived at the repository"),
        ("callSign", "string", "Force call sign"),
        ("forceType", "string", "Force type or reporting platform"),
        ("unit", "string", "Organizational unit"),
        ("netId", "string", "Force/network identifier"),
        ("pstn", "string", "Force telephone number"),
        ("sourceType", "string", "Report source"),
        ("id", "string", "Unique event identifier"),
        ("trigger", "string", "Event type or trigger"),
        ("locationType", "string", "Polygon/location type"),
    )

    def build(self, layer: LayerMeta, rows: List[dict]) -> LayerSchema:
        declared = [self._declared_field(item, rows) for item in self._FIELDS]
        fields = declared + self._extra_fields(declared, rows)
        return LayerSchema(
            layer_id=layer.id,
            geometry_type="Geometry",
            fields=fields,
            source_name="Our Forces",
            source_description="Tyche own-force events and geographic positions",
            temporal_field="eventTime",
        )

    def _declared_field(self, item: tuple, rows: List[dict]) -> LayerField:
        name, field_type, description = item
        return LayerField(
            name=name,
            type=field_type,
            description=description,
            samples=self._samples(rows, name),
        )

    def _extra_fields(
        self, declared: List[LayerField], rows: List[dict]
    ) -> List[LayerField]:
        known = {field.name for field in declared}
        names = dict.fromkeys(
            str(key) for row in rows for key in row if key != "geometry"
        )
        return [
            LayerField(name=name, type="string", samples=self._samples(rows, name))
            for name in names
            if name not in known
        ]

    def _samples(self, rows: List[dict], name: str) -> List[str]:
        values = [
            str(row[name])[:self._MAX_SAMPLE_CHARS]
            for row in rows
            if row.get(name) is not None
        ]
        return list(dict.fromkeys(values))[:5]
