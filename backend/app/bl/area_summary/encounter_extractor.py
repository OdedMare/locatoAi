import geopandas as gpd
import pandas as pd

from app.bl.area_summary.extractor_support import (
    clean_value,
    evidence_for,
    format_time,
    normalized_time,
    require_field,
)
from app.bl.area_summary.layer_config import resolved_field
from app.bl.area_summary.models.fact import AreaSummaryFact
from app.common.utils.geo_utils import metric_crs_for, to_metric

_MAX_FACTS = 100


def extract_encounter_facts(
    data, layer, schema, distance_m, time_tolerance_minutes,
):
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
    metric = _metric_points(data, entity_field, name_field)
    matches = _latest_matches(metric, distance_m, time_tolerance_minutes)
    return [
        _encounter_fact(match, layer)
        for match in sorted(
            matches.values(), key=lambda item: item["observed"], reverse=True
        )[:_MAX_FACTS]
    ]


def _metric_points(data, entity_field, name_field):
    usable = data.dropna(
        subset=[entity_field, name_field, "_summary_time", data.geometry.name]
    ).copy()
    if not usable.empty and not usable.geometry.geom_type.eq("Point").all():
        raise ValueError("Encounter summary requires point observations")
    points = gpd.GeoDataFrame({
        "entity": usable[entity_field].map(str),
        "name": usable[name_field].map(str),
        "time": usable["_summary_time"],
        "evidence_id": usable["_summary_evidence_id"],
    }, geometry=usable.geometry, crs=usable.crs).reset_index(drop=True)
    return to_metric(points, metric_crs_for(points)) if not points.empty else points


def _latest_matches(data, distance_m, tolerance_minutes):
    matches = {}
    tolerance = pd.Timedelta(minutes=tolerance_minutes)
    for left_index, left in data.iterrows():
        candidates = data.sindex.query(
            left.geometry.buffer(distance_m), predicate="intersects"
        )
        for right_index in candidates:
            if int(right_index) <= left_index:
                continue
            match = _candidate(left, data.iloc[int(right_index)], tolerance)
            if match is not None:
                _keep_latest(matches, match)
    return matches


def _candidate(left, right, tolerance):
    if left["entity"] == right["entity"]:
        return None
    delta = abs(left["time"] - right["time"])
    if delta > tolerance:
        return None
    observed = max(left["time"], right["time"])
    return {
        "pair": tuple(sorted((left["entity"], right["entity"]))),
        "left": left, "right": right, "observed": observed,
        "distance": float(left.geometry.distance(right.geometry)),
    }


def _keep_latest(matches, candidate):
    current = matches.get(candidate["pair"])
    if current is None or (
        candidate["observed"], -candidate["distance"]
    ) > (current["observed"], -current["distance"]):
        matches[candidate["pair"]] = candidate


def _encounter_fact(match, layer):
    left, right = match["left"], match["right"]
    names = [clean_value(left["name"]), clean_value(right["name"])]
    observed = normalized_time(match["observed"])
    text = "{} ו{} נצפו במרחק {} מטר זה מזה סביב {}.".format(
        names[0], names[1], round(match["distance"]),
        format_time(match["observed"]),
    )
    return AreaSummaryFact(
        kind="encounter", layer_id=layer.id, layer_name=layer.name,
        text=text, count=2, entities=names, observed_at=observed,
        evidence=[
            _encounter_evidence(left), _encounter_evidence(right),
        ],
    )


def _encounter_evidence(row):
    mapped = {
        "_summary_evidence_id": row["evidence_id"],
        "_summary_time": row["time"],
    }
    return evidence_for(mapped, row["entity"])
