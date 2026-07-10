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
        if step.direction == "north":
            order = centroids.y.sort_values(ascending=False)
        elif step.direction == "south":
            order = centroids.y.sort_values(ascending=True)
        elif step.direction == "east":
            order = centroids.x.sort_values(ascending=False)
        else:  # "west" — directions are closed by the Literal type
            order = centroids.x.sort_values(ascending=True)
        return gdf.loc[order.index[: step.count]]
