import geopandas as gpd
import pandas as pd

from app.bl.executor.ops.base import ExecutionContext, OpHandler, register_op
from app.bl.plan.models.movement_direction_step import MovementDirectionStep
from app.common.errors import ExecutionError
from app.common.geo import metric_crs_for, to_metric


def _matches(direction: str, dx: float, dy: float) -> bool:
    vertical = direction in ("north", "south")
    if vertical and abs(dy) < abs(dx):
        return False
    if not vertical and abs(dx) < abs(dy):
        return False
    axis = dy if vertical else dx
    return axis > 0 if direction in ("north", "east") else axis < 0


@register_op("movement_direction")
class MovementDirectionOp(OpHandler):
    def run(self, step: MovementDirectionStep,
            ctx: ExecutionContext) -> gpd.GeoDataFrame:
        data = ctx.results[step.input].copy()
        self._validate(data, step)
        data["_time"] = pd.to_datetime(data[step.time_field], utc=True, errors="coerce")
        data = data.dropna(subset=[step.entity_field, "_time"]).sort_values("_time")
        metric = to_metric(data, metric_crs_for(data))
        positions, distances = self._moving_entities(metric, step)
        result = data.iloc[positions].copy()
        result["movement_distance_m"] = distances
        result["movement_direction"] = step.direction
        return result.drop(columns=["_time"])

    def _validate(self, data: gpd.GeoDataFrame, step: MovementDirectionStep) -> None:
        missing = {step.entity_field, step.time_field} - set(data.columns)
        if missing:
            raise ExecutionError(f"movement_direction missing fields: {sorted(missing)}")

    def _moving_entities(self, data: gpd.GeoDataFrame,
                         step: MovementDirectionStep):
        positions, distances = [], []
        for _, group in data.groupby(step.entity_field, sort=False):
            if len(group) < 2:
                continue
            first, last = group.iloc[0], group.iloc[-1]
            dx, dy = last.geometry.x - first.geometry.x, last.geometry.y - first.geometry.y
            distance = float((dx * dx + dy * dy) ** 0.5)
            if distance >= step.min_distance_m and _matches(step.direction, dx, dy):
                positions.append(data.index.get_loc(group.index[-1]))
                distances.append(round(distance, 2))
        return positions, distances
