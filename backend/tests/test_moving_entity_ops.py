from types import SimpleNamespace

import geopandas as gpd
from shapely.geometry import Point

from app.bl.executor.ops.latest_per_entity import LatestPerEntityOp
from app.bl.executor.ops.movement_direction import MovementDirectionOp
from app.bl.plan.models.latest_per_entity_step import LatestPerEntityStep
from app.bl.plan.models.movement_direction_step import MovementDirectionStep


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
