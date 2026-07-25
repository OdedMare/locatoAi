"""Score subject features by how many rule features surround them."""

import geopandas as gpd

from app.bl.ranking.models.contribution import RankingContribution
from app.bl.ranking.rule_config import numeric_field, weight
from app.bl.ranking.rule_support import bounded_evidence, clamp_unit
from app.common.utils.geo_utils import metric_crs_for, to_metric


def score_density(subjects, rule_data, layer):
    """Return {subject index: RankingContribution} for a density rule."""
    radius_m = numeric_field(layer, "distance_m", 500.0)
    saturation = numeric_field(layer, "saturation_count", 10.0)
    if radius_m <= 0 or saturation <= 0:
        raise ValueError("Ranking density radius and saturation must be positive")
    if rule_data.empty or subjects.empty:
        return {}
    counts = _counts(subjects, rule_data, radius_m)
    return _contributions(counts, rule_data, layer, radius_m, saturation)


def _counts(subjects, rule_data, radius_m):
    metric_crs = metric_crs_for(subjects, rule_data)
    left = to_metric(subjects[["geometry"]], metric_crs)
    right = to_metric(rule_data[["geometry"]], metric_crs)
    buffered = gpd.GeoDataFrame(
        {"geometry": left.geometry.buffer(radius_m)}, crs=metric_crs
    )
    joined = gpd.sjoin(buffered, right, predicate="intersects", how="left")
    return joined.groupby(level=0)["index_right"].count()


def _contributions(counts, rule_data, layer, radius_m, saturation):
    rule_weight = weight(layer)
    return {
        index: _contribution(
            int(count), rule_data, layer, radius_m, saturation, rule_weight
        )
        for index, count in counts.items()
        if count > 0
    }


def _contribution(count, rule_data, layer, radius_m, saturation, rule_weight):
    raw = clamp_unit(count / saturation)
    return RankingContribution(
        kind="density", rule_layer_id=layer.id, rule_layer_name=layer.name,
        text="{} ישויות מ{} ברדיוס {} מטר.".format(
            count, layer.name, int(round(radius_m))
        ),
        weight=rule_weight, raw_score=raw, weighted_score=raw * rule_weight,
        matched_count=count, evidence=bounded_evidence(rule_data),
    )
