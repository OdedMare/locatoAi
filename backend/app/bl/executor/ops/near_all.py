"""Proximity to every reference in a multi-layer relationship query."""

from typing import Dict, List

import geopandas as gpd

from app.bl.executor.ops.base.execution_context import ExecutionContext
from app.bl.executor.ops.base.op_handler import OpHandler
from app.bl.executor.ops.base.op_registry import register_op
from app.bl.executor.ops.near import (
    DISTANCE_COLUMN,
    MATCH_REASON_COLUMN,
    _feature_from_row,
    filter_reference_entities,
)
from app.bl.plan.models.near_all_step import NearAllStep
from app.common.utils.geo_utils import metric_crs_for, to_metric

MATCHED_TARGETS_COLUMN = "matched_reference_features"
TARGET_DISTANCES_COLUMN = "distance_to_targets_m"


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
        targets = self._load_targets(step, ctx)
        if gdf.empty or targets is None:
            return self._empty_result(gdf)
        distances, references, eligible = self._match_all(gdf, targets, step)
        if not eligible:
            return self._empty_result(gdf)
        return self._build_result(
            gdf, step, distances, references, eligible
        )

    @staticmethod
    def _load_targets(step: NearAllStep, ctx: ExecutionContext):
        targets = []
        for spec in step.targets:
            target = filter_reference_entities(
                ctx.load_layer_features(
                    spec.layer,
                    geometry_hint=ctx.proximity_geometry(step.distance_m),
                ),
                spec.field,
                spec.operator,
                spec.value,
            )
            if target.empty:
                return None
            targets.append((spec, target))
        return targets

    def _match_all(self, gdf, targets, step):
        metric_crs = metric_crs_for(gdf, *(target for _, target in targets))
        left = to_metric(gdf, metric_crs)
        distances: Dict[object, List[dict]] = {index: [] for index in gdf.index}
        references: Dict[object, List[dict]] = {index: [] for index in gdf.index}
        eligible = set(gdf.index)
        for spec, target in targets:
            nearest = self._nearest(left, target, eligible, metric_crs, step.distance_m)
            eligible &= set(nearest.index)
            if not eligible:
                break
            self._record_matches(
                gdf, spec, target, nearest, eligible, distances, references
            )
        return distances, references, eligible

    @staticmethod
    def _nearest(left, target, eligible, metric_crs, distance_m):
        right = to_metric(target[["geometry"]], metric_crs)
        joined = gpd.sjoin_nearest(
            left.loc[[index for index in left.index if index in eligible]],
            right, max_distance=distance_m, how="inner",
            distance_col="_distance_m",
        )
        return joined.sort_values("_distance_m").loc[
            lambda frame: ~frame.index.duplicated(keep="first")
        ]

    @staticmethod
    def _record_matches(
        gdf, spec, target, nearest, eligible, distances, references,
    ) -> None:
        remaining = [index for index in gdf.index if index in eligible]
        for index, row in nearest.loc[remaining].iterrows():
            distance = float(row["_distance_m"])
            distances[index].append({"layer_id": spec.layer, "distance_m": distance})
            references[index].append(_feature_from_row(target.loc[row["index_right"]]))

    def _build_result(self, gdf, step, distances, references, eligible):
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
        self._add_reasons(result, step)
        result = result.sort_values(DISTANCE_COLUMN, kind="stable")
        return result.head(step.count) if step.count is not None else result

    @staticmethod
    def _add_reasons(result, step) -> None:
        result[MATCH_REASON_COLUMN] = [
            f"נמצא בטווח {round(float(step.distance_m))} מ׳ מכל "
            f"{len(step.targets)} ישויות הייחוס; מרחק ממוצע "
            f"{round(float(score))} מ׳."
            for score in result[DISTANCE_COLUMN]
        ]

    @staticmethod
    def _empty_result(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        result = gdf.iloc[0:0].copy()
        for column in (
            DISTANCE_COLUMN, MATCH_REASON_COLUMN,
            MATCHED_TARGETS_COLUMN, TARGET_DISTANCES_COLUMN,
        ):
            result[column] = []
        return result
