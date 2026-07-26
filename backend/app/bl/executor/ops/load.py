import geopandas as gpd

from app.bl.executor.ops.base.execution_context import ExecutionContext
from app.bl.executor.ops.base.op_handler import OpHandler
from app.bl.executor.ops.base.op_registry import register_op
from app.bl.plan.models.load_step import LoadStep


@register_op("load")
class LoadOp(OpHandler):
    def run(self, step: LoadStep, ctx: ExecutionContext) -> gpd.GeoDataFrame:
        # When the request carries boundaries, push them down as a
        # provider-side spatial filter hint so the whole layer isn't
        # fetched just to be cut down by within_geometry afterwards.
        return ctx.load_layer_features(
            step.layer,
            temporal_range=ctx.load_temporal_ranges.get(step.id),
            attribute_filters=ctx.load_attribute_filters.get(step.id),
        )
