import geopandas as gpd

from app.bl.executor.ops.base.execution_context import ExecutionContext
from app.bl.executor.ops.base.op_handler import OpHandler
from app.bl.executor.ops.base.op_registry import register_op
from app.bl.plan.models.within_geometry_step import WithinGeometryStep
from app.common.errors.execution_error import ExecutionError
from app.common.geo import WGS84, require_crs


@register_op("within_geometry")
class WithinGeometryOp(OpHandler):
    def run(self, step: WithinGeometryStep, ctx: ExecutionContext) -> gpd.GeoDataFrame:
        if ctx.user_geometry is None:
            # Validators reject this earlier; guard for direct engine use.
            raise ExecutionError("within_geometry requires request boundaries")
        gdf = ctx.results[step.input]
        try:
            require_crs(gdf, "within_geometry")
        except ValueError as exc:
            raise ExecutionError(str(exc)) from exc
        # user_geometry is always WGS84 (built straight from the request's
        # GeoJSON boundaries — see dto.py). A provider whose features come
        # back in a different CRS would otherwise intersect silently wrong
        # (or empty) with no error — reproject defensively before comparing.
        if gdf.crs is not None and str(gdf.crs) != WGS84:
            gdf = gdf.to_crs(WGS84)
        # `intersects` (not `within`): a feature partially inside the drawn
        # area still counts — matches user intuition for lines/polygons.
        return gdf[gdf.geometry.intersects(ctx.user_geometry)]
