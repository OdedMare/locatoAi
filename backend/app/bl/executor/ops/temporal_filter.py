import pandas as pd
import geopandas as gpd

from app.bl.executor.ops.base.execution_context import ExecutionContext
from app.bl.executor.ops.base.op_handler import OpHandler
from app.bl.executor.ops.base.op_registry import register_op
from app.bl.plan.models.temporal_filter_step import TemporalFilterStep
from app.common.errors.execution_error import ExecutionError


@register_op("temporal_filter")
class TemporalFilterOp(OpHandler):
    def run(self, step: TemporalFilterStep, ctx: ExecutionContext) -> gpd.GeoDataFrame:
        gdf = ctx.results[step.input]
        if gdf.empty:
            return gdf
        field = self._temporal_field(gdf)
        timestamps = pd.to_datetime(gdf[field], utc=True, errors="coerce")
        start, end = self._range(step)
        return gdf[(timestamps >= start) & (timestamps <= end)]

    @staticmethod
    def _temporal_field(gdf) -> str:
        field = gdf.attrs.get("temporal_field")
        if field is None:
            raise ExecutionError("temporal_filter: layer has no temporal field")
        if field not in gdf.columns:
            raise ExecutionError(f"temporal_filter: layer has no '{field}' field")
        return field

    @staticmethod
    def _range(step):
        try:
            start = pd.to_datetime(step.from_, utc=True)
            end = pd.to_datetime(step.to, utc=True)
        except (TypeError, ValueError) as exc:
            raise ExecutionError(f"temporal_filter: invalid date range: {exc}") from exc
        if start > end:
            raise ExecutionError("temporal_filter: 'from' must not be after 'to'")
        return start, end
