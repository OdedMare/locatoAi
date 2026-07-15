"""Proximity to every reference in a multi-layer relationship query."""

from typing import Dict, List

import geopandas as gpd

from app.bl.executor.ops.base import ExecutionContext, OpHandler, register_op
from app.bl.executor.ops.near import (
    DISTANCE_COLUMN,
    MATCH_REASON_COLUMN,
    _feature_from_row,
    filter_reference_entities,
)
from app.bl.plan.models.near_all_step import NearAllStep
from app.common.geo import metric_crs_for, to_metric

MATCHED_TARGETS_COLUMN = "matched_reference_features"
TARGET_DISTANCES_COLUMN = "distance_to_targets_m"


def _empty_result(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    result = gdf.iloc[0:0].copy()
    for column in (
        DISTANCE_COLUMN,
        MATCH_REASON_COLUMN,
        MATCHED_TARGETS_COLUMN,
        TARGET_DISTANCES_COLUMN,
    ):
        result[column] = []
    return result


@register_op("near_all")
class NearAllOp(OpHandler):
    """Require proximity to ALL targets, then optionally rank and limit.

    Ranking uses the mean distance to all references. This avoids letting a
    feature extremely close to one reference win while being far from the
    others, and keeps the meaning intuitive for queries such as "the two
    soldiers near the square and the school".
    """

    def run(self, step: NearAllStep, ctx: ExecutionContext) -> gpd.GeoDataFrame:
        gdf = ctx.results[step.input]
        targets = []
        for spec in step.targets:
            target = filter_reference_entities(
                ctx.load_layer_features(spec.layer),
                spec.field,
                spec.operator,
                spec.value,
            )
            if target.empty:
                return _empty_result(gdf)
            targets.append((spec, target))
        if gdf.empty:
            return _empty_result(gdf)

        metric_crs = metric_crs_for(gdf, *(target for _, target in targets))
        left = to_metric(gdf, metric_crs)
        distances: Dict[object, List[dict]] = {index: [] for index in gdf.index}
        references: Dict[object, List[dict]] = {index: [] for index in gdf.index}
        eligible = set(gdf.index)

        for spec, target in targets:
            right = to_metric(target[["geometry"]], metric_crs)
            joined = gpd.sjoin_nearest(
                left.loc[[index for index in gdf.index if index in eligible]],
                right,
                max_distance=step.distance_m,
                how="inner",
                distance_col="_distance_m",
            )
            nearest = joined.sort_values("_distance_m").loc[
                lambda frame: ~frame.index.duplicated(keep="first")
            ]
            eligible &= set(nearest.index)
            if not eligible:
                return _empty_result(gdf)
            remaining = [index for index in gdf.index if index in eligible]
            for index, row in nearest.loc[remaining].iterrows():
                distance = float(row["_distance_m"])
                distances[index].append(
                    {"layer_id": spec.layer, "distance_m": distance}
                )
                references[index].append(
                    _feature_from_row(target.loc[row["index_right"]])
                )

        result = gdf.loc[
            [index for index in gdf.index if index in eligible]
        ].copy()
        result[TARGET_DISTANCES_COLUMN] = [distances[index] for index in result.index]
        result[MATCHED_TARGETS_COLUMN] = [references[index] for index in result.index]
        result[DISTANCE_COLUMN] = [
            sum(item["distance_m"] for item in distances[index])
            / len(distances[index])
            for index in result.index
        ]
        result[MATCH_REASON_COLUMN] = [
            f"נמצא בטווח {round(float(step.distance_m))} מ׳ מכל "
            f"{len(step.targets)} ישויות הייחוס; מרחק ממוצע "
            f"{round(float(score))} מ׳."
            for score in result[DISTANCE_COLUMN]
        ]
        result = result.sort_values(DISTANCE_COLUMN, kind="stable")
        if step.count is not None:
            result = result.head(step.count)
        return result
