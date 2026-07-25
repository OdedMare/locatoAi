"""Score subject features by distance to a hazard/reference layer."""

import geopandas as gpd

from app.bl.ranking.models.contribution import RankingContribution
from app.bl.ranking.rule_config import direction, numeric_field, weight
from app.bl.ranking.rule_support import bounded_evidence, clamp_unit
from app.common.utils.geo_utils import metric_crs_for, to_metric


def score_proximity(subjects, rule_data, layer):
    """Return {subject index: RankingContribution} for a proximity rule."""
    radius_m = numeric_field(layer, "distance_m", 500.0)
    if radius_m <= 0:
        raise ValueError("Ranking rank:distance_m must be positive")
    if rule_data.empty or subjects.empty:
        return {}
    distances = _distances(subjects, rule_data)
    return _contributions(distances, rule_data, layer, radius_m)


def _distances(subjects, rule_data):
    metric_crs = metric_crs_for(subjects, rule_data)
    left = to_metric(subjects[["geometry"]], metric_crs)
    right = to_metric(rule_data[["geometry"]], metric_crs)
    union = right.geometry.unary_union
    return gpd.GeoSeries(left.geometry, crs=metric_crs).distance(union)


def _contributions(distances, rule_data, layer, radius_m):
    rule_weight = weight(layer)
    closer_is_worse = direction(layer) == "closer_is_worse"
    return {
        index: _contribution(
            distance, rule_data, layer, radius_m, rule_weight, closer_is_worse
        )
        for index, distance in distances.items()
        if distance <= radius_m
    }


def _contribution(
    distance, rule_data, layer, radius_m, rule_weight, closer_is_worse
):
    ratio = clamp_unit(distance / radius_m)
    raw = 1.0 - ratio if closer_is_worse else ratio
    return RankingContribution(
        kind="proximity", rule_layer_id=layer.id, rule_layer_name=layer.name,
        text=_text(layer, distance, radius_m),
        weight=rule_weight, raw_score=raw, weighted_score=raw * rule_weight,
        measured_distance_m=round(float(distance), 2),
        evidence=bounded_evidence(rule_data),
    )


def _text(layer, distance, radius_m):
    return "מרחק {} מטר מ{} (סף {} מטר).".format(
        int(round(distance)), layer.name, int(round(radius_m))
    )
