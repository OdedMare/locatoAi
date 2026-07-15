import geopandas as gpd

from app.bl.executor.ops.base.execution_context import ExecutionContext
from app.bl.executor.ops.base.op_handler import OpHandler
from app.bl.executor.ops.base.op_registry import register_op
from app.bl.plan.models.directional_step import DirectionalStep
from app.common.geo import WGS84, require_crs


@register_op("directional")
class DirectionalOp(OpHandler):
    """Take the `count` most-northern/southern/eastern/western features."""

    def run(self, step: DirectionalStep, ctx: ExecutionContext) -> gpd.GeoDataFrame:
        gdf = ctx.results[step.input]
        if gdf.empty:
            return gdf

        # Rank by each feature's WGS84 bounding-box center. Unlike a fixed
        # projected CRS, this remains meaningful for datasets outside Israel.
        require_crs(gdf, "directional")
        bounds = gdf.to_crs(WGS84).geometry.bounds
        x = (bounds.minx + bounds.maxx) / 2
        y = (bounds.miny + bounds.maxy) / 2
        if step.direction == "north":
            order = y.sort_values(ascending=False, kind="stable")
        elif step.direction == "south":
            order = y.sort_values(ascending=True, kind="stable")
        elif step.direction == "east":
            order = x.sort_values(ascending=False, kind="stable")
        else:  # "west" — directions are closed by the Literal type
            order = x.sort_values(ascending=True, kind="stable")
        return gdf.loc[order.index[: step.count]]
