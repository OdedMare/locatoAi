import geopandas as gpd

from app.bl.executor.ops.base import ExecutionContext, OpHandler, register_op
from app.bl.executor.ops.near import DISTANCE_COLUMN
from app.bl.plan.models import NearestNStep
from app.common.geo import to_metric


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
        target = ctx.load_layer_features(step.target_layer)
        if gdf.empty or target.empty:
            result = gdf.iloc[0:0].copy()
            result[DISTANCE_COLUMN] = []
            return result

        left = to_metric(gdf)
        right = to_metric(target[["geometry"]])
        # No max_distance — nearest_n ranks globally, it isn't a threshold.
        joined = gpd.sjoin_nearest(left, right, distance_col=DISTANCE_COLUMN)
        nearest = joined.groupby(level=0)[DISTANCE_COLUMN].min()

        # count > available rows degrades gracefully (nsmallest returns
        # everything), same precedent as DirectionalStep's index slice.
        top_n = nearest.nsmallest(step.count)
        result = gdf.loc[top_n.index].copy()
        result[DISTANCE_COLUMN] = top_n
        return result
