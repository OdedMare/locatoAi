import geopandas as gpd

from app.bl.executor.ops.base import ExecutionContext, OpHandler, register_op
from app.bl.plan.models import WithinGeometryStep
from app.common.errors import ExecutionError


@register_op("within_geometry")
class WithinGeometryOp(OpHandler):
    def run(self, step: WithinGeometryStep, ctx: ExecutionContext) -> gpd.GeoDataFrame:
        if ctx.user_geometry is None:
            # Validators reject this earlier; guard for direct engine use.
            raise ExecutionError("within_geometry requires request boundaries")
        gdf = ctx.results[step.input]
        # `intersects` (not `within`): a feature partially inside the drawn
        # area still counts — matches user intuition for lines/polygons.
        return gdf[gdf.geometry.intersects(ctx.user_geometry)]
