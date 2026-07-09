import geopandas as gpd

from app.bl.executor.ops.base import ExecutionContext, OpHandler, register_op
from app.bl.plan.models import DirectionalStep
from app.common.geo import to_metric


@register_op("directional")
class DirectionalOp(OpHandler):
    """Take the `count` most-northern/southern/eastern/western features."""

    def run(self, step: DirectionalStep, ctx: ExecutionContext) -> gpd.GeoDataFrame:
        gdf = ctx.results[step.input]
        if gdf.empty:
            return gdf

        # Centroid in a projected CRS (WGS84 centroids are inaccurate and
        # geopandas warns); order is what matters here.
        centroids = to_metric(gdf).geometry.centroid
        match step.direction:
            case "north":
                order = centroids.y.sort_values(ascending=False)
            case "south":
                order = centroids.y.sort_values(ascending=True)
            case "east":
                order = centroids.x.sort_values(ascending=False)
            case "west":
                order = centroids.x.sort_values(ascending=True)
        return gdf.loc[order.index[: step.count]]
