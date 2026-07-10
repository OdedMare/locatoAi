import geopandas as gpd

from app.bl.executor.ops.base import ExecutionContext, OpHandler, register_op
from app.bl.plan.models import NearStep
from app.common.geo import to_metric


@register_op("near")
class NearOp(OpHandler):
    """Keep input features within distance_m of ANY target-layer feature.

    Locked decision: meters math never happens in WGS84 degrees — both
    layers are reprojected to ITM (EPSG:2039) first.
    """

    def run(self, step: NearStep, ctx: ExecutionContext) -> gpd.GeoDataFrame:
        gdf = ctx.results[step.input]
        target = ctx.load_layer_features(step.target_layer)
        if gdf.empty or target.empty:
            return gdf.iloc[0:0]

        left = to_metric(gdf)
        right = to_metric(target[["geometry"]])
        joined = gpd.sjoin_nearest(left, right, max_distance=step.distance_m, how="inner")
        # sjoin_nearest can duplicate a left row when several targets tie.
        matched_index = joined.index.unique()
        return gdf.loc[matched_index]
