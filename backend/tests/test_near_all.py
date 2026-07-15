from types import SimpleNamespace

import geopandas as gpd
from shapely.geometry import Point

from app.bl.executor.ops.near_all import NearAllOp
from app.bl.plan.models.near_all_step import NearAllStep


def frame(names, points):
    return gpd.GeoDataFrame(
        {"name": names, "geometry": points}, geometry="geometry", crs="EPSG:4326"
    )


def test_near_all_requires_every_reference_ranks_and_limits():
    subjects = frame(
        ["best", "second", "third", "only-near-first"],
        [
            Point(34.001, 32.0),
            Point(34.001, 32.0002),
            Point(34.001, 32.0005),
            Point(34.00005, 32.0),
        ],
    )
    targets = {
        "squares": frame(["square"], [Point(34.0, 32.0)]),
        "schools": frame(["school"], [Point(34.002, 32.0)]),
    }
    ctx = SimpleNamespace(
        results={"input": subjects},
        load_layer_features=lambda layer_id: targets[layer_id],
    )
    step = NearAllStep.model_validate({
        "id": "s2",
        "op": "near_all",
        "input": "input",
        "targets": [{"layer": "squares"}, {"layer": "schools"}],
        "distance_m": 180,
        "count": 2,
    })

    result = NearAllOp().run(step, ctx)

    assert list(result["name"]) == ["best", "second"]
    assert result["distance_to_target_m"].is_monotonic_increasing
    assert result["matched_reference_features"].map(len).eq(2).all()
    assert result.geometry.notna().all()
    assert "2 ישויות" in result.iloc[0]["match_reason"]


def test_near_all_empty_when_one_required_reference_has_no_match():
    subjects = frame(["soldier"], [Point(34.0, 32.0)])
    targets = {
        "squares": frame(["square"], [Point(34.0, 32.0)]),
        "schools": frame(["school"], [Point(35.0, 33.0)]),
    }
    ctx = SimpleNamespace(
        results={"input": subjects},
        load_layer_features=lambda layer_id: targets[layer_id],
    )
    step = NearAllStep.model_validate({
        "id": "s2", "op": "near_all", "input": "input",
        "targets": [{"layer": "squares"}, {"layer": "schools"}],
        "distance_m": 300, "count": 2,
    })

    result = NearAllOp().run(step, ctx)

    assert result.empty
    assert "matched_reference_features" in result.columns
