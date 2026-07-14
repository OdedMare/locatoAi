import geopandas as gpd

from app.bl.executor.ops.base import ExecutionContext, OpHandler, register_op
from app.bl.plan.models import NearStep
from app.common.geo import to_metric

# Computed distance to the nearest target-layer feature, in meters — added
# as a plain column so it survives every downstream op unchanged and is
# serialized into the GeoJSON response like any other property.
DISTANCE_COLUMN = "distance_to_target_m"


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
            result = gdf.iloc[0:0].copy()
            result[DISTANCE_COLUMN] = []
            return result

        left = to_metric(gdf)
        right = to_metric(target[["geometry"]])
        joined = gpd.sjoin_nearest(
            left, right, max_distance=step.distance_m, how="inner",
            distance_col=DISTANCE_COLUMN,
        )
        # Several targets can tie within range — keep the nearest per row.
        nearest = joined.groupby(level=0)[DISTANCE_COLUMN].min()
        result = gdf.loc[nearest.index].copy()
        result[DISTANCE_COLUMN] = nearest
        return result
