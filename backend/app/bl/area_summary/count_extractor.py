from app.bl.area_summary.extractor_support import (
    bounded_evidence,
    clean_value,
    require_field,
)
from app.bl.area_summary.layer_config import configured_field
from app.bl.area_summary.models.fact import AreaSummaryFact


def extract_count_facts(data, layer, _schema):
    if data.empty:
        return []
    group_field = configured_field(layer, "group_field")
    if not group_field:
        return [_count_fact(data, layer)]
    require_field(data, group_field, "group")
    return [
        _count_fact(group, layer, clean_value(value))
        for value, group in data.groupby(group_field, dropna=True, sort=True)
        if clean_value(value)
    ]


def _count_fact(data, layer, group=""):
    count = len(data)
    text = (
        "נמצאו {} ישויות מסוג {}.".format(count, group)
        if group else "נמצאו {} ישויות בשכבת {}.".format(count, layer.name)
    )
    return AreaSummaryFact(
        kind="count", layer_id=layer.id, layer_name=layer.name,
        text=text, count=count, evidence=bounded_evidence(data),
    )
