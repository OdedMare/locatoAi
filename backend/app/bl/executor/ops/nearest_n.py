import geopandas as gpd

from app.bl.executor.ops.base.execution_context import ExecutionContext
from app.bl.executor.ops.base.op_handler import OpHandler
from app.bl.executor.ops.base.op_registry import register_op
from app.bl.executor.ops.near import (
    DISTANCE_COLUMN,
    MATCH_REASON_COLUMN,
    NEAREST_TARGET_COLUMN,
    enrich_proximity_results,
    filter_reference_entities,
)
from app.bl.plan.models.nearest_n_step import NearestNStep
from app.common.geo import metric_crs_for, to_metric


@register_op("nearest_n")
class NearestNOp(OpHandler):
    """Keep the `count` input features globally closest to ANY target-layer
    feature — not threshold-based like `near`, a flat top-N over all rows.

    Each input row's distance is to its own nearest target-layer feature
    (sjoin_nearest + groupby-min to collapse ties, same as near.py), then
    the N smallest of those per-row distances win.
    """

    def run(self, step: NearestNStep, ctx: ExecutionContext) -> gpd.GeoDataFrame:
        gdf = ctx.results[step.input]
        target = self._target(step, ctx)
        if gdf.empty or target.empty:
            return self._empty(gdf)
        nearest_rows = self._nearest_rows(gdf, target)
        top_n = nearest_rows.nsmallest(step.count, DISTANCE_COLUMN)
        return enrich_proximity_results(gdf, target, top_n)

    @staticmethod
    def _target(step: NearestNStep, ctx: ExecutionContext):
        target = ctx.load_layer_features(step.target_layer)
        return filter_reference_entities(
            target, step.target_field, step.target_operator, step.target_value
        )

    @staticmethod
    def _nearest_rows(gdf, target):
        metric_crs = metric_crs_for(gdf, target)
        left = to_metric(gdf, metric_crs)
        right = to_metric(target[["geometry"]], metric_crs)
        joined = gpd.sjoin_nearest(left, right, distance_col=DISTANCE_COLUMN)
        return joined.sort_values(DISTANCE_COLUMN).loc[
            lambda frame: ~frame.index.duplicated(keep="first")
        ]

    @staticmethod
    def _empty(gdf):
        result = gdf.iloc[0:0].copy()
        result[DISTANCE_COLUMN] = []
        result[MATCH_REASON_COLUMN] = []
        result[NEAREST_TARGET_COLUMN] = []
        return result
