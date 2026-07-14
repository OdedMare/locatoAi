import pandas as pd
import geopandas as gpd

from app.bl.executor.ops.base import ExecutionContext, OpHandler, register_op
from app.bl.plan.models import TemporalFilterStep
from app.common.errors import ExecutionError


@register_op("temporal_filter")
class TemporalFilterOp(OpHandler):
    def run(self, step: TemporalFilterStep, ctx: ExecutionContext) -> gpd.GeoDataFrame:
        gdf = ctx.results[step.input]
        if gdf.empty:
            return gdf

        # Set by ExecutionContext.load_layer_features from the layer's
        # provider-reported schema — not a hardcoded column name, since
        # different providers name their event-time field differently
        # (mock: "timestamp"; MQS: "date" or a per-layer tag override).
        field = gdf.attrs.get("temporal_field")
        if field is None:
            raise ExecutionError("temporal_filter: layer has no temporal field")
        if field not in gdf.columns:
            raise ExecutionError(f"temporal_filter: layer has no '{field}' field")

        timestamps = pd.to_datetime(gdf[field], utc=True, errors="coerce")
        start = pd.to_datetime(step.from_, utc=True)
        end = pd.to_datetime(step.to, utc=True)
        return gdf[(timestamps >= start) & (timestamps <= end)]
