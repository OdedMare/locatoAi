import geopandas as gpd

from app.bl.executor.ops.base import ExecutionContext, OpHandler, register_op
from app.bl.plan.models.load_step import LoadStep


@register_op("load")
class LoadOp(OpHandler):
    def run(self, step: LoadStep, ctx: ExecutionContext) -> gpd.GeoDataFrame:
        # When the request carries boundaries, push them down as a
        # provider-side spatial filter hint so the whole layer isn't
        # fetched just to be cut down by within_geometry afterwards.
        return ctx.load_layer_features(step.layer, push_down_geometry=True)
