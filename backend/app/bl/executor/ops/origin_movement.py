import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, mapping

from app.bl.executor.ops.base.execution_context import ExecutionContext
from app.bl.executor.ops.base.op_handler import OpHandler
from app.bl.executor.ops.base.op_registry import register_op
from app.bl.plan.models.origin_movement_step import OriginMovementStep
from app.common.errors.execution_error import ExecutionError
from app.common.utils.geo_utils import metric_crs_for, to_metric


@register_op("origin_movement")
class OriginMovementOp(OpHandler):
    _RESULT_COLUMNS = (
        "origin_movement",
        "origin_inferred_from",
        "origin_departure_distance_m",
        "origin_return_distance_m",
        "movement_path_distance_m",
        "movement_path",
    )

    def run(self, step: OriginMovementStep,
            ctx: ExecutionContext) -> gpd.GeoDataFrame:
        data = self._prepare(ctx.results[step.input], step)
        if data.empty:
            return self._empty(data)
        start_at, end_at = self._times(step)
        metric = to_metric(data, metric_crs_for(data))
        matches = self._matches(data, metric, step, start_at, end_at)
        return self._result(data, matches, step)

    def _prepare(self, source, step):
        missing = {step.entity_field, step.time_field} - set(source.columns)
        if missing:
            raise ExecutionError(
                f"origin_movement missing fields: {sorted(missing)}"
            )
        if not source.empty and not source.geometry.geom_type.eq("Point").all():
            raise ExecutionError("origin_movement requires point observations")
        data = source.copy()
        data["_time"] = pd.to_datetime(
            data[step.time_field], utc=True, errors="coerce"
        )
        return data.dropna(
            subset=[step.entity_field, "_time", data.geometry.name]
        ).sort_values("_time").reset_index(drop=True)

    @staticmethod
    def _times(step):
        try:
            start_at = pd.to_datetime(step.start_at, utc=True)
            end_at = pd.to_datetime(step.end_at, utc=True)
        except (TypeError, ValueError) as exc:
            raise ExecutionError(f"origin_movement invalid time: {exc}") from exc
        if start_at >= end_at:
            raise ExecutionError("origin_movement start_at must be before end_at")
        return start_at, end_at

    def _matches(self, source, metric, step, start_at, end_at):
        matches = []
        for _, group in metric.groupby(step.entity_field, sort=False):
            match = self._entity_match(
                source, group, step, start_at, end_at
            )
            if match is not None:
                matches.append(match)
        return matches

    def _entity_match(self, source, group, step, start_at, end_at):
        group = group[
            (group["_time"] >= start_at) & (group["_time"] <= end_at)
        ]
        if group.empty:
            return None
        start = self._nearest(group, start_at, step.time_tolerance_minutes)
        end = self._end_index(group, step, end_at)
        if start is None or end is None or start >= end:
            return None
        segment = group.loc[start:end]
        if len(segment) < (3 if step.pattern == "round_trip" else 2):
            return None
        departure, returned, path = self._distances(segment)
        if departure < step.min_departure_distance_m:
            return None
        if (
            step.pattern == "round_trip"
            and returned > step.max_return_distance_m
        ):
            return None
        return self._match(source, segment, departure, returned, path)

    def _end_index(self, group, step, end_at):
        if step.pattern == "departed":
            return group.index[-1]
        return self._nearest(group, end_at, step.time_tolerance_minutes)

    @staticmethod
    def _nearest(group, target, tolerance_minutes):
        deltas = (group["_time"] - target).abs()
        index = deltas.idxmin()
        if deltas.loc[index] > pd.Timedelta(minutes=tolerance_minutes):
            return None
        return index

    @staticmethod
    def _distances(segment):
        points = list(segment.geometry)
        departure = max(points[0].distance(point) for point in points)
        returned = points[0].distance(points[-1])
        path = sum(left.distance(right) for left, right in zip(points, points[1:]))
        return float(departure), float(returned), float(path)

    @staticmethod
    def _match(source, segment, departure, returned, path):
        indices = list(segment.index)
        coordinates = [
            (point.x, point.y) for point in source.loc[indices].geometry
        ]
        return {
            "index": indices[-1],
            "departure": round(departure, 2),
            "returned": round(returned, 2),
            "path_distance": round(path, 2),
            "path": mapping(LineString(coordinates)),
        }

    def _result(self, data, matches, step):
        if not matches:
            return self._empty(data)
        result = data.loc[[item["index"] for item in matches]].copy()
        result["origin_movement"] = step.pattern
        result["origin_inferred_from"] = "first_observation_near_start_at"
        result["origin_departure_distance_m"] = [
            item["departure"] for item in matches
        ]
        result["origin_return_distance_m"] = [
            item["returned"] for item in matches
        ]
        result["movement_path_distance_m"] = [
            item["path_distance"] for item in matches
        ]
        result["movement_path"] = [item["path"] for item in matches]
        return result.drop(columns=["_time"])

    def _empty(self, data):
        result = data.iloc[0:0].drop(columns=["_time"], errors="ignore").copy()
        for column in self._RESULT_COLUMNS:
            result[column] = []
        return result
