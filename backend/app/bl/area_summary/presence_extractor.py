from app.bl.area_summary.extractor_support import (
    clean_value,
    evidence_for,
    format_time,
    normalized_time,
    require_field,
)
from app.bl.area_summary.layer_config import resolved_field
from app.bl.area_summary.models.fact import AreaSummaryFact

_MAX_FACTS = 100


def extract_presence_facts(data, layer, schema):
    if data.empty:
        return []
    entity_field = require_field(
        data, layer.entity_field or schema.entity_field, "entity"
    )
    name_field = require_field(
        data,
        resolved_field(
            layer, schema, "name_field",
            layer.display_field, schema.display_field, entity_field,
        ),
        "name",
    )
    require_field(data, "_summary_time", "time")
    latest = _latest_rows(data, entity_field)
    return [
        _presence_fact(row, layer, entity_field, name_field)
        for _, row in latest.head(_MAX_FACTS).iterrows()
    ]


def _latest_rows(data, entity_field):
    usable = data.dropna(subset=[entity_field, "_summary_time"])
    return usable.sort_values("_summary_time", ascending=False).drop_duplicates(
        entity_field, keep="first"
    )


def _presence_fact(row, layer, entity_field, name_field):
    name = clean_value(row[name_field]) or clean_value(row[entity_field])
    observed = normalized_time(row["_summary_time"])
    return AreaSummaryFact(
        kind="presence", layer_id=layer.id, layer_name=layer.name,
        text="{} נצפה כאן לאחרונה ב-{}.".format(
            name, format_time(row["_summary_time"])
        ),
        count=1, entities=[name], observed_at=observed,
        evidence=[evidence_for(row, row[entity_field])],
    )
