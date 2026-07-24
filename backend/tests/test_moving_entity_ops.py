from types import SimpleNamespace

import geopandas as gpd
from shapely.geometry import Point

from app.bl.executor.ops.latest_per_entity import LatestPerEntityOp
from app.bl.executor.ops.movement_direction import MovementDirectionOp
from app.bl.executor.ops.origin_movement import OriginMovementOp
from app.bl.executor.ops.trajectory_relation import TrajectoryRelationOp
from app.bl.plan.models.latest_per_entity_step import LatestPerEntityStep
from app.bl.plan.models.movement_direction_step import MovementDirectionStep
from app.bl.plan.models.origin_movement_step import OriginMovementStep
from app.bl.plan.models.trajectory_relation_step import TrajectoryRelationStep


def observations():
    return gpd.GeoDataFrame({
        "netId": ["bus-south", "bus-south", "bus-north", "bus-north", "single"],
        "eventTime": [
            "2026-07-15T09:00:00Z", "2026-07-15T10:00:00Z",
            "2026-07-15T09:00:00Z", "2026-07-15T10:00:00Z",
            "2026-07-15T10:00:00Z",
        ],
    }, geometry=[
        Point(34.78, 32.10), Point(34.78, 32.08),
        Point(34.79, 32.08), Point(34.79, 32.10),
        Point(34.80, 32.09),
    ], crs="EPSG:4326")


def test_latest_per_entity_returns_one_newest_observation():
    ctx = SimpleNamespace(results={"input": observations()})
    step = LatestPerEntityStep(id="latest", op="latest_per_entity", input="input")
    result = LatestPerEntityOp().run(step, ctx)
    assert len(result) == 3
    assert result.loc[result["netId"] == "bus-south"].geometry.iloc[0].y == 32.08


def test_movement_direction_returns_latest_matching_vehicle_position():
    ctx = SimpleNamespace(results={"input": observations()})
    step = MovementDirectionStep(id="move", op="movement_direction", input="input",
                                 direction="south", min_distance_m=100)
    result = MovementDirectionOp().run(step, ctx)
    assert list(result["netId"]) == ["bus-south"]
    assert result.geometry.iloc[0].y == 32.08
    assert result.iloc[0]["movement_distance_m"] > 100
    assert result.iloc[0]["movement_path"] == {
        "type": "LineString",
        "coordinates": ((34.78, 32.10), (34.78, 32.08)),
    }


def test_movement_direction_ignores_single_observation_entities():
    ctx = SimpleNamespace(results={"input": observations()})
    step = MovementDirectionStep(id="move", op="movement_direction", input="input",
                                 direction="west", min_distance_m=0)
    assert MovementDirectionOp().run(step, ctx).empty


def test_movement_without_direction_uses_traveled_path():
    data = gpd.GeoDataFrame({
        "netId": ["patrol", "patrol", "patrol"],
        "eventTime": [
            "2026-07-15T09:00:00Z", "2026-07-15T09:30:00Z",
            "2026-07-15T10:00:00Z",
        ],
    }, geometry=[
        Point(34.78, 32.10), Point(34.78, 32.08), Point(34.78, 32.10),
    ], crs="EPSG:4326")
    ctx = SimpleNamespace(results={"input": data})
    step = MovementDirectionStep(
        id="move", op="movement_direction", input="input",
        direction="any", min_distance_m=100,
    )

    result = MovementDirectionOp().run(step, ctx)

    assert list(result["netId"]) == ["patrol"]
    assert result.iloc[0]["movement_distance_m"] > 100
    assert result.iloc[0]["movement_direction"] == "any"


def relation_observations():
    return gpd.GeoDataFrame({
        "friendId": [
            "alice", "alice", "alice",
            "bob", "bob", "bob",
            "far", "far", "far",
        ],
        "seenAt": [
            "2026-07-15T09:00:00Z", "2026-07-15T09:10:00Z",
            "2026-07-15T09:20:00Z",
            "2026-07-15T09:02:00Z", "2026-07-15T09:12:00Z",
            "2026-07-15T09:22:00Z",
            "2026-07-15T09:00:00Z", "2026-07-15T09:10:00Z",
            "2026-07-15T09:20:00Z",
        ],
    }, geometry=[
        Point(34.7800, 32.1000), Point(34.7810, 32.1000),
        Point(34.7820, 32.1000),
        Point(34.7801, 32.1001), Point(34.7811, 32.1001),
        Point(34.7821, 32.1001),
        Point(34.8000, 32.1200), Point(34.8010, 32.1200),
        Point(34.8020, 32.1200),
    ], crs="EPSG:4326")


def run_relation(data, relation, **overrides):
    values = {
        "id": "relation", "op": "trajectory_relation", "input": "input",
        "relation": relation, "entity_field": "friendId",
        "time_field": "seenAt", "min_movement_distance_m": 50,
    }
    values.update(overrides)
    step = TrajectoryRelationStep(**values)
    return TrajectoryRelationOp().run(
        step, SimpleNamespace(results={"input": data})
    )


def test_trajectory_relation_finds_friends_moving_together_with_buffers():
    result = run_relation(
        relation_observations(), "together",
        max_distance_m=30, time_tolerance_minutes=3,
        max_gap_minutes=15, min_duration_minutes=15,
    )

    assert set(result["friendId"]) == {"alice", "bob"}
    assert result.set_index("friendId").loc["alice", "related_entity_ids"] == ["bob"]
    assert set(result["relation_duration_minutes"]) == {20}
    assert all(result["movement_distance_m"] > 100)


def test_together_prefers_spatial_match_inside_the_time_buffer():
    data = gpd.GeoDataFrame({
        "friendId": ["alice", "alice", "bob", "bob", "bob", "bob"],
        "seenAt": [
            "2026-07-15T09:00:00Z", "2026-07-15T09:10:00Z",
            "2026-07-15T09:00:00Z", "2026-07-15T09:01:00Z",
            "2026-07-15T09:10:00Z", "2026-07-15T09:11:00Z",
        ],
    }, geometry=[
        Point(34.7800, 32.1000), Point(34.7820, 32.1000),
        Point(34.8000, 32.1200), Point(34.7801, 32.1001),
        Point(34.8000, 32.1200), Point(34.7821, 32.1001),
    ], crs="EPSG:4326")

    result = run_relation(
        data, "together", max_distance_m=30,
        time_tolerance_minutes=2, min_duration_minutes=5,
    )

    assert set(result["friendId"]) == {"alice", "bob"}


def test_trajectory_relation_finds_same_destination_with_arrival_buffer():
    data = gpd.GeoDataFrame({
        "friendId": ["alice", "alice", "bob", "bob", "late", "late"],
        "seenAt": [
            "2026-07-15T09:00:00Z", "2026-07-15T09:20:00Z",
            "2026-07-15T09:05:00Z", "2026-07-15T09:23:00Z",
            "2026-07-15T09:00:00Z", "2026-07-15T10:00:00Z",
        ],
    }, geometry=[
        Point(34.7800, 32.1000), Point(34.7900, 32.1000),
        Point(34.8000, 32.1100), Point(34.7901, 32.1001),
        Point(34.8100, 32.1200), Point(34.7901, 32.1001),
    ], crs="EPSG:4326")

    result = run_relation(
        data, "same_destination",
        max_distance_m=30, time_tolerance_minutes=5,
    )

    assert set(result["friendId"]) == {"alice", "bob"}
    assert set(result["relation_time_delta_minutes"]) == {3}


def test_trajectory_relation_finds_movement_at_same_time_with_buffer():
    data = gpd.GeoDataFrame({
        "friendId": ["alice", "alice", "bob", "bob", "late", "late"],
        "seenAt": [
            "2026-07-15T09:00:00Z", "2026-07-15T09:10:00Z",
            "2026-07-15T09:14:00Z", "2026-07-15T09:24:00Z",
            "2026-07-15T10:00:00Z", "2026-07-15T10:10:00Z",
        ],
    }, geometry=[
        Point(34.780, 32.100), Point(34.790, 32.100),
        Point(34.800, 32.110), Point(34.810, 32.110),
        Point(34.820, 32.120), Point(34.830, 32.120),
    ], crs="EPSG:4326")

    result = run_relation(data, "same_time", time_tolerance_minutes=5)

    assert set(result["friendId"]) == {"alice", "bob"}
    assert set(result["relation_time_delta_minutes"]) == {4}


def test_trajectory_relation_finds_same_place_at_different_times():
    data = gpd.GeoDataFrame({
        "friendId": ["alice", "alice", "bob", "bob", "far", "far"],
        "seenAt": [
            "2026-07-15T09:00:00Z", "2026-07-15T09:10:00Z",
            "2026-07-15T09:50:00Z", "2026-07-15T10:00:00Z",
            "2026-07-15T09:30:00Z", "2026-07-15T10:00:00Z",
        ],
    }, geometry=[
        Point(34.780, 32.100), Point(34.7900, 32.1000),
        Point(34.800, 32.110), Point(34.7901, 32.1001),
        Point(34.820, 32.120), Point(34.8300, 32.1200),
    ], crs="EPSG:4326")

    result = run_relation(
        data, "same_place_different_times",
        max_distance_m=30, min_time_separation_minutes=30,
    )

    assert set(result["friendId"]) == {"alice", "bob"}
    assert set(result["relation_time_delta_minutes"]) == {50}


def origin_observations():
    return gpd.GeoDataFrame({
        "personKey": [
            "returned", "returned", "returned",
            "departed", "departed", "departed",
            "stayed", "stayed", "stayed",
        ],
        "observed": [
            "2026-07-15T20:00:00Z", "2026-07-15T20:30:00Z",
            "2026-07-15T21:00:00Z",
            "2026-07-15T20:00:00Z", "2026-07-15T20:30:00Z",
            "2026-07-15T21:00:00Z",
            "2026-07-15T20:00:00Z", "2026-07-15T20:30:00Z",
            "2026-07-15T21:00:00Z",
        ],
    }, geometry=[
        Point(34.780, 32.100), Point(34.790, 32.100),
        Point(34.7801, 32.1001),
        Point(34.800, 32.110), Point(34.810, 32.110),
        Point(34.812, 32.110),
        Point(34.820, 32.120), Point(34.8201, 32.1201),
        Point(34.8201, 32.1201),
    ], crs="EPSG:4326")


def run_origin(pattern):
    step = OriginMovementStep(
        id="origin", op="origin_movement", input="input", pattern=pattern,
        start_at="2026-07-15T20:00:00Z", end_at="2026-07-15T21:00:00Z",
        entity_field="personKey", time_field="observed",
        time_tolerance_minutes=5, min_departure_distance_m=500,
        max_return_distance_m=50,
    )
    return OriginMovementOp().run(
        step, SimpleNamespace(results={"input": origin_observations()})
    )


def test_origin_movement_detects_round_trip_with_non_netid_identity():
    result = run_origin("round_trip")

    assert list(result["personKey"]) == ["returned"]
    assert result.iloc[0]["origin_movement"] == "round_trip"
    assert result.iloc[0]["origin_return_distance_m"] < 50


def test_origin_movement_detects_night_departures_and_marks_inferred_origin():
    result = run_origin("departed")

    assert set(result["personKey"]) == {"returned", "departed"}
    assert set(result["origin_inferred_from"]) == {
        "first_observation_near_start_at"
    }
