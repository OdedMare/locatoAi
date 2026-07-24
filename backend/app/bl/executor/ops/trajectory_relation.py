from itertools import combinations

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, mapping

from app.bl.executor.ops.base.execution_context import ExecutionContext
from app.bl.executor.ops.base.op_handler import OpHandler
from app.bl.executor.ops.base.op_registry import register_op
from app.bl.plan.models.trajectory_relation_step import TrajectoryRelationStep
from app.common.errors.execution_error import ExecutionError
from app.common.utils.geo_utils import metric_crs_for, to_metric


@register_op("trajectory_relation")
class TrajectoryRelationOp(OpHandler):
    _RESULT_COLUMNS = (
        "trajectory_relation",
        "related_entity_ids",
        "relation_distance_m",
        "relation_time_delta_minutes",
        "relation_duration_minutes",
        "movement_distance_m",
        "movement_path",
    )

    def run(self, step: TrajectoryRelationStep,
            ctx: ExecutionContext) -> gpd.GeoDataFrame:
        data = self._prepare(ctx.results[step.input], step)
        if data.empty:
            return self._empty(data)
        metric = to_metric(data, metric_crs_for(data))
        trajectories = self._trajectories(metric, step)
        pairs = self._pair_matches(metric, trajectories, step)
        return self._result(data, trajectories, pairs, step)

    @staticmethod
    def _prepare(source, step):
        missing = {step.entity_field, step.time_field} - set(source.columns)
        if missing:
            raise ExecutionError(
                f"trajectory_relation missing fields: {sorted(missing)}"
            )
        if not source.empty and not source.geometry.geom_type.eq("Point").all():
            raise ExecutionError("trajectory_relation requires point observations")
        data = source.copy()
        data["_time"] = pd.to_datetime(
            data[step.time_field], utc=True, errors="coerce"
        )
        data = data.dropna(
            subset=[step.entity_field, "_time", data.geometry.name]
        )
        data["_entity_key"] = data[step.entity_field].map(str)
        return data.sort_values(["_entity_key", "_time"]).reset_index(drop=True)

    def _trajectories(self, metric, step):
        trajectories = {}
        for key, group in metric.groupby("_entity_key", sort=False):
            indices = list(group.index)
            distance = self._path_distance(group.geometry)
            if len(indices) >= 2 and distance >= step.min_movement_distance_m:
                trajectories[key] = {
                    "indices": indices,
                    "distance": distance,
                    "start": indices[0],
                    "end": indices[-1],
                }
        return trajectories

    @staticmethod
    def _path_distance(points):
        points = list(points)
        return float(sum(
            left.distance(right) for left, right in zip(points, points[1:])
        ))

    def _pair_matches(self, metric, trajectories, step):
        matcher = {
            "together": self._together,
            "same_destination": self._same_destination,
            "same_time": self._same_time,
            "same_place_different_times": self._same_place_different_times,
        }[step.relation]
        matches = []
        # ponytail: pairwise scan is simple; add spatiotemporal indexing if profiling
        # shows large moving-entity layers make this relation a bottleneck.
        for (left_key, left), (right_key, right) in combinations(
            trajectories.items(), 2
        ):
            match = matcher(metric, left_key, left, right_key, right, step)
            if match is not None:
                matches.append(match)
        return matches

    def _together(self, data, left_key, left, right_key, right, step):
        aligned = self._aligned(data, left, right, step)
        sessions = self._sessions(aligned, step.max_gap_minutes)
        candidates = [
            self._together_session(data, session, left_key, right_key, step)
            for session in sessions
        ]
        candidates = [item for item in candidates if item is not None]
        return max(
            candidates, key=lambda item: item["duration"], default=None
        )

    def _aligned(self, data, left, right, step):
        matches = []
        tolerance = pd.Timedelta(minutes=step.time_tolerance_minutes)
        for left_index in left["indices"]:
            candidates = self._time_candidates(
                data, left_index, right["indices"], tolerance
            )
            if not candidates:
                continue
            right_index = min(candidates, key=lambda index: (
                abs(data.loc[index, "_time"] - data.loc[left_index, "_time"]),
                data.geometry.loc[index].distance(data.geometry.loc[left_index]),
            ))
            distance = data.geometry.loc[left_index].distance(
                data.geometry.loc[right_index]
            )
            if distance <= step.max_distance_m:
                matches.append(self._aligned_match(
                    data, left_index, right_index, distance
                ))
        return matches

    @staticmethod
    def _time_candidates(data, index, other_indices, tolerance):
        time = data.loc[index, "_time"]
        return [
            other for other in other_indices
            if abs(data.loc[other, "_time"] - time) <= tolerance
        ]

    @staticmethod
    def _aligned_match(data, left, right, distance):
        left_time, right_time = data.loc[left, "_time"], data.loc[right, "_time"]
        return {
            "time": max(left_time, right_time),
            "indices": (left, right),
            "distance": float(distance),
            "time_delta": abs(left_time - right_time).total_seconds() / 60,
        }

    @staticmethod
    def _sessions(matches, max_gap_minutes):
        sessions, current = [], []
        for match in sorted(matches, key=lambda item: item["time"]):
            if current and match["time"] - current[-1]["time"] > pd.Timedelta(
                minutes=max_gap_minutes
            ):
                sessions.append(current)
                current = []
            current.append(match)
        return sessions + ([current] if current else [])

    def _together_session(self, data, session, left_key, right_key, step):
        duration = (
            session[-1]["time"] - session[0]["time"]
        ).total_seconds() / 60
        left_indices = [item["indices"][0] for item in session]
        right_indices = [item["indices"][1] for item in session]
        if duration < step.min_duration_minutes:
            return None
        if self._path_distance(data.geometry.loc[left_indices]) < (
            step.min_movement_distance_m
        ):
            return None
        if self._path_distance(data.geometry.loc[right_indices]) < (
            step.min_movement_distance_m
        ):
            return None
        return self._record(
            left_key, right_key, left_indices[-1], right_indices[-1],
            max(item["distance"] for item in session),
            max(item["time_delta"] for item in session), duration,
        )

    def _same_destination(self, data, left_key, left, right_key, right, step):
        left_index, right_index = left["end"], right["end"]
        distance = data.geometry.loc[left_index].distance(
            data.geometry.loc[right_index]
        )
        delta = self._time_delta(data, left_index, right_index)
        if distance > step.max_distance_m:
            return None
        if delta > step.time_tolerance_minutes:
            return None
        return self._record(
            left_key, right_key, left_index, right_index, distance, delta, 0
        )

    def _same_time(self, data, left_key, left, right_key, right, step):
        candidates = []
        for left_segment in self._segments(data, left):
            for right_segment in self._segments(data, right):
                gap, overlap = self._interval_relation(
                    left_segment, right_segment
                )
                if gap <= step.time_tolerance_minutes:
                    candidates.append((gap, overlap, left_segment, right_segment))
        candidates = [
            item for item in candidates if item[1] >= step.min_duration_minutes
        ]
        if not candidates:
            return None
        gap, overlap, left_segment, right_segment = max(
            candidates, key=lambda item: (item[1], -item[0])
        )
        return self._record(
            left_key, right_key, left_segment["end_index"],
            right_segment["end_index"], 0, gap, overlap,
        )

    @staticmethod
    def _segments(data, trajectory):
        result = []
        for start, end in zip(
            trajectory["indices"], trajectory["indices"][1:]
        ):
            if data.geometry.loc[start].equals(data.geometry.loc[end]):
                continue
            result.append({
                "start": data.loc[start, "_time"],
                "end": data.loc[end, "_time"],
                "end_index": end,
            })
        return result

    @staticmethod
    def _interval_relation(left, right):
        start, end = max(left["start"], right["start"]), min(
            left["end"], right["end"]
        )
        overlap = max(0, (end - start).total_seconds() / 60)
        if left["end"] < right["start"]:
            gap = (right["start"] - left["end"]).total_seconds() / 60
        elif right["end"] < left["start"]:
            gap = (left["start"] - right["end"]).total_seconds() / 60
        else:
            gap = 0
        return gap, overlap

    def _same_place_different_times(
        self, data, left_key, left, right_key, right, step
    ):
        candidates = []
        for left_index in left["indices"]:
            for right_index in right["indices"]:
                distance = data.geometry.loc[left_index].distance(
                    data.geometry.loc[right_index]
                )
                delta = self._time_delta(data, left_index, right_index)
                if (
                    distance <= step.max_distance_m
                    and delta >= step.min_time_separation_minutes
                ):
                    candidates.append(
                        (distance, delta, left_index, right_index)
                    )
        if not candidates:
            return None
        distance, delta, left_index, right_index = min(candidates)
        return self._record(
            left_key, right_key, left_index, right_index, distance, delta, 0
        )

    @staticmethod
    def _time_delta(data, left_index, right_index):
        return abs(
            data.loc[left_index, "_time"] - data.loc[right_index, "_time"]
        ).total_seconds() / 60

    @staticmethod
    def _record(left, right, left_index, right_index,
                distance, time_delta, duration):
        return {
            "entities": (left, right),
            "indices": (left_index, right_index),
            "distance": float(distance),
            "time_delta": float(time_delta),
            "duration": float(duration),
        }

    def _result(self, data, trajectories, pairs, step):
        if not pairs:
            return self._empty(data)
        entities = self._entity_results(data, pairs)
        keys = sorted(entities)
        result = data.loc[[entities[key]["index"] for key in keys]].copy()
        result["trajectory_relation"] = step.relation
        result["related_entity_ids"] = [
            sorted(entities[key]["related"]) for key in keys
        ]
        result["relation_distance_m"] = [
            round(min(entities[key]["distances"]), 2) for key in keys
        ]
        result["relation_time_delta_minutes"] = [
            round(min(entities[key]["time_deltas"]), 2) for key in keys
        ]
        result["relation_duration_minutes"] = [
            round(max(entities[key]["durations"]), 2) for key in keys
        ]
        return self._movement_columns(
            result, data, trajectories, entities, keys
        )

    @staticmethod
    def _entity_results(data, pairs):
        result = {}
        for pair in pairs:
            for position, key in enumerate(pair["entities"]):
                item = result.setdefault(key, {
                    "index": pair["indices"][position], "related": set(),
                    "distances": [], "time_deltas": [], "durations": [],
                })
                candidate = pair["indices"][position]
                if data.loc[candidate, "_time"] > data.loc[item["index"], "_time"]:
                    item["index"] = candidate
                item["related"].add(pair["entities"][1 - position])
                item["distances"].append(pair["distance"])
                item["time_deltas"].append(pair["time_delta"])
                item["durations"].append(pair["duration"])
        return result

    @staticmethod
    def _movement_columns(result, data, trajectories, entities, keys):
        result["movement_distance_m"] = [
            round(trajectories[key]["distance"], 2) for key in keys
        ]
        result["movement_path"] = [
            mapping(LineString([
                (point.x, point.y)
                for point in data.geometry.loc[trajectories[key]["indices"]]
            ]))
            for key in keys
        ]
        return result.drop(columns=["_time", "_entity_key"])

    def _empty(self, data):
        result = data.iloc[0:0].drop(
            columns=["_time", "_entity_key"], errors="ignore"
        ).copy()
        for column in self._RESULT_COLUMNS:
            result[column] = []
        return result
