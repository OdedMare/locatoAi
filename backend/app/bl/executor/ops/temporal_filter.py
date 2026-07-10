import pandas as pd
import geopandas as gpd

from app.bl.executor.ops.base import ExecutionContext, OpHandler, register_op
from app.bl.plan.models import TemporalFilterStep
from app.common.errors import ExecutionError

# MVP convention: temporal layers expose their event time in this field.
# v0.2: the field name should come from the provider schema.
TIMESTAMP_FIELD = "timestamp"


@register_op("temporal_filter")
class TemporalFilterOp(OpHandler):
    def run(self, step: TemporalFilterStep, ctx: ExecutionContext) -> gpd.GeoDataFrame:
        gdf = ctx.results[step.input]
        if gdf.empty:
            return gdf
        if TIMESTAMP_FIELD not in gdf.columns:
            raise ExecutionError(
                f"temporal_filter: layer has no '{TIMESTAMP_FIELD}' field"
            )

        timestamps = pd.to_datetime(gdf[TIMESTAMP_FIELD], utc=True, errors="coerce")
        start = pd.to_datetime(step.from_, utc=True)
        end = pd.to_datetime(step.to, utc=True)
        return gdf[(timestamps >= start) & (timestamps <= end)]
