import geopandas as gpd
import pandas as pd

from app.bl.executor.ops.base import ExecutionContext, OpHandler, register_op
from app.bl.plan.models import LatestPerEntityStep
from app.common.errors import ExecutionError


@register_op("latest_per_entity")
class LatestPerEntityOp(OpHandler):
    def run(self, step: LatestPerEntityStep,
            ctx: ExecutionContext) -> gpd.GeoDataFrame:
        data = ctx.results[step.input]
        missing = {step.entity_field, step.time_field} - set(data.columns)
        if missing:
            raise ExecutionError(f"latest_per_entity missing fields: {sorted(missing)}")
        result = data.copy()
        result["_observation_time"] = pd.to_datetime(result[step.time_field], utc=True,
                                                      errors="coerce")
        result = result.dropna(subset=[step.entity_field, "_observation_time"])
        result = result.sort_values("_observation_time").drop_duplicates(
            step.entity_field, keep="last")
        return result.drop(columns=["_observation_time"])
