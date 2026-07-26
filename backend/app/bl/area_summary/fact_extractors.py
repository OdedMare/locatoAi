from app.bl.area_summary.count_extractor import extract_count_facts
from app.bl.area_summary.encounter_extractor import extract_encounter_facts
from app.bl.area_summary.presence_extractor import extract_presence_facts
from app.bl.area_summary.recommendation_extractor import (
    extract_recommendation_facts,
)


def extract_facts(
    kind, data, layer, schema, encounter_distance_m,
    encounter_time_tolerance_minutes,
):
    if kind == "count":
        return extract_count_facts(data, layer, schema)
    if kind == "presence":
        return extract_presence_facts(data, layer, schema)
    if kind == "recommendation":
        return extract_recommendation_facts(data, layer, schema)
    return extract_encounter_facts(
        data, layer, schema, encounter_distance_m,
        encounter_time_tolerance_minutes,
    )
