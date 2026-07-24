import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, mapping

from app.bl.executor.ops.base.execution_context import ExecutionContext
from app.bl.executor.ops.base.op_handler import OpHandler
from app.bl.executor.ops.base.op_registry import register_op
from app.bl.plan.models.round_trip_step import RoundTripStep
from app.common.errors.execution_error import ExecutionError
from app.common.utils.geo_utils import metric_crs_for, to_metric


@register_op("round_trip")
class RoundTripOp(OpHandler):
    _RESULT_COLUMNS = (
        "round_trip_departure_distance_m",
        "round_trip_return_distance_m",
        "round_trip_path_distance_m",
        "round_trip_path",
    )

    def run(self, step: RoundTripStep,
            ctx: ExecutionContext) -> gpd.GeoDataFrame:
        data = self._prepare(ctx.results[step.input], step)
        if data.empty:
            return self._empty(data)
        depart_at, return_at = self._times(step)
        metric = to_metric(data, metric_crs_for(data))
        matches = self._matches(data, metric, step, depart_at, return_at)
        return self._result(data, matches)

    def _prepare(self, source, step):
        missing = {step.entity_field, step.time_field} - set(source.columns)
        if missing:
            raise ExecutionError(f"round_trip missing fields: {sorted(missing)}")
        if not source.empty and not source.geometry.geom_type.eq("Point").all():
            raise ExecutionError("round_trip requires point observations")
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
            depart_at = pd.to_datetime(step.depart_at, utc=True)
            return_at = pd.to_datetime(step.return_at, utc=True)
        except (TypeError, ValueError) as exc:
            raise ExecutionError(f"round_trip invalid time: {exc}") from exc
        if depart_at >= return_at:
            raise ExecutionError("round_trip depart_at must be before return_at")
        return depart_at, return_at

    def _matches(self, source, metric, step, depart_at, return_at):
        matches = []
        for _, group in metric.groupby(step.entity_field, sort=False):
            match = self._entity_match(
                source, group, step, depart_at, return_at
            )
            if match is not None:
                matches.append(match)
        return matches

    def _entity_match(self, source, group, step, depart_at, return_at):
        start = self._nearest(group, depart_at, step.time_tolerance_minutes)
        end = self._nearest(group, return_at, step.time_tolerance_minutes)
        if start is None or end is None or start >= end:
            return None
        segment = group.loc[start:end]
        if len(segment) < 3:
            return None
        departure, returned, path = self._distances(segment)
        if departure < step.min_departure_distance_m:
            return None
        if returned > step.max_return_distance_m:
            return None
        return self._match(source, segment, departure, returned, path)

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

    def _result(self, data, matches):
        if not matches:
            return self._empty(data)
        result = data.loc[[item["index"] for item in matches]].copy()
        result["round_trip_departure_distance_m"] = [
            item["departure"] for item in matches
        ]
        result["round_trip_return_distance_m"] = [
            item["returned"] for item in matches
        ]
        result["round_trip_path_distance_m"] = [
            item["path_distance"] for item in matches
        ]
        result["round_trip_path"] = [item["path"] for item in matches]
        return result.drop(columns=["_time"])

    def _empty(self, data):
        result = data.iloc[0:0].drop(columns=["_time"], errors="ignore").copy()
        for column in self._RESULT_COLUMNS:
            result[column] = []
        return result
