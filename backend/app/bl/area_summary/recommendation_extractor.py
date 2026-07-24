from app.bl.area_summary.extractor_support import (
    clean_value,
    evidence_for,
    normalized_time,
    require_field,
)
from app.bl.area_summary.layer_config import configured_field, resolved_field
from app.bl.area_summary.models.fact import AreaSummaryFact

_MAX_FACTS = 100


def extract_recommendation_facts(data, layer, schema):
    text_field = require_field(
        data,
        resolved_field(
            layer, schema, "text_field",
            layer.display_field, schema.display_field,
        ),
        "recommendation text",
    )
    owner_field = configured_field(layer, "owner_field") or (
        layer.entity_field or schema.entity_field
    )
    source_field = configured_field(layer, "source_field")
    _validate_optional(data, owner_field, "owner")
    _validate_optional(data, source_field, "source")
    return [
        _recommendation_fact(row, layer, text_field, owner_field, source_field)
        for _, row in data.head(_MAX_FACTS).iterrows()
        if clean_value(row[text_field])
    ]


def _validate_optional(data, field, role):
    if field:
        require_field(data, field, role)


def _recommendation_fact(row, layer, text_field, owner_field, source_field):
    label = clean_value(row[text_field])
    owner = clean_value(row.get(owner_field)) if owner_field else ""
    source = clean_value(row.get(source_field)) if source_field else ""
    text = "נמצאה המלצה על {}.".format(label)
    text += " נשמרה על ידי {}.".format(owner) if owner else ""
    text += " מקור: {}.".format(source) if source else ""
    return AreaSummaryFact(
        kind="recommendation", layer_id=layer.id, layer_name=layer.name,
        text=text, count=1, entities=[owner] if owner else [],
        observed_at=normalized_time(row.get("_summary_time")),
        evidence=[evidence_for(row, row.get(owner_field) if owner_field else None)],
    )
