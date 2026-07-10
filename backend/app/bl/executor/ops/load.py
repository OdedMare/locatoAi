import geopandas as gpd

from app.bl.executor.ops.base import ExecutionContext, OpHandler, register_op
from app.bl.plan.models import LoadStep


@register_op("load")
class LoadOp(OpHandler):
    def run(self, step: LoadStep, ctx: ExecutionContext) -> gpd.GeoDataFrame:
        return ctx.load_layer_features(step.layer)
