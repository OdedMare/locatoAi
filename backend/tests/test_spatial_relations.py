from types import SimpleNamespace

import geopandas as gpd
from shapely.geometry import LineString, Point, Polygon

from app.bl.executor.ops.between import BetweenOp
from app.bl.executor.ops.spatial_relation.contains_op import ContainsOp
from app.bl.executor.ops.spatial_relation.crosses_op import CrossesOp
from app.bl.executor.ops.spatial_relation.touches_op import TouchesOp
from app.bl.plan.models.between_step import BetweenStep
from app.bl.plan.models.contains_step import ContainsStep
from app.bl.plan.models.crosses_step import CrossesStep
from app.bl.plan.models.touches_step import TouchesStep


def frame(names, geometries):
    return gpd.GeoDataFrame(
        {"name": names, "geometry": geometries}, geometry="geometry", crs="EPSG:4326"
    )


def context(subject, targets):
    return SimpleNamespace(
        results={"input": subject},
        load_layer_features=lambda layer_id, geometry_hint=None: targets[layer_id],
        proximity_geometry=lambda distance_m: None,
    )


def test_crosses_keeps_only_geometries_crossing_reference():
    subject = frame(
        ["crossing", "separate"],
        [LineString([(-1, 0), (1, 0)]), LineString([(-1, 2), (1, 2)])],
    )
    target = frame(["road"], [LineString([(0, -1), (0, 1)])])
    step = CrossesStep(id="x", op="crosses", input="input", target_layer="target")

    result = CrossesOp().run(step, context(subject, {"target": target}))

    assert list(result["name"]) == ["crossing"]
    assert result.geometry.notna().all()


def test_touches_excludes_overlaps_and_keeps_boundary_contact():
    subject = frame(
        ["touching", "overlapping"],
        [
            Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
            Polygon([(0.5, 0), (1.5, 0), (1.5, 1), (0.5, 1)]),
        ],
    )
    target = frame(
        ["area"], [Polygon([(1, 0), (2, 0), (2, 1), (1, 1)])]
    )
    step = TouchesStep(id="t", op="touches", input="input", target_layer="target")

    result = TouchesOp().run(step, context(subject, {"target": target}))

    assert list(result["name"]) == ["touching"]


def test_contains_respects_relation_direction():
    subject = frame(
        ["container", "outside"],
        [
            Polygon([(0, 0), (2, 0), (2, 2), (0, 2)]),
            Polygon([(3, 3), (4, 3), (4, 4), (3, 4)]),
        ],
    )
    target = frame(["place"], [Point(1, 1)])
    step = ContainsStep(id="c", op="contains", input="input", target_layer="target")

    result = ContainsOp().run(step, context(subject, {"target": target}))

    assert list(result["name"]) == ["container"]


def test_between_uses_meter_corridor_between_two_references():
    subject = frame(
        ["between", "outside"],
        [Point(34.005, 32.0), Point(34.005, 32.01)],
    )
    first = frame(["a"], [Point(34.0, 32.0)])
    second = frame(["b"], [Point(34.01, 32.0)])
    step = BetweenStep(
        id="b",
        op="between",
        input="input",
        first_target_layer="first",
        second_target_layer="second",
        corridor_width_m=100,
    )

    result = BetweenOp().run(
        step, context(subject, {"first": first, "second": second})
    )

    assert list(result["name"]) == ["between"]
    assert "100" in result.iloc[0]["match_reason"]


def test_between_buffers_target_fetches_by_corridor_width():
    """Both reference layers must be fetched using a geometry hint buffered
    by corridor_width_m — avoids pulling the whole target layer for large
    MQS/Cubes layers when only a narrow corridor around the request matters."""
    subject = frame(["between"], [Point(34.005, 32.0)])
    first = frame(["a"], [Point(34.0, 32.0)])
    second = frame(["b"], [Point(34.01, 32.0)])
    step = BetweenStep(
        id="b", op="between", input="input",
        first_target_layer="first", second_target_layer="second",
        corridor_width_m=250,
    )

    calls = []
    ctx = SimpleNamespace(
        results={"input": subject},
        load_layer_features=lambda layer_id, geometry_hint=None: (
            calls.append((layer_id, geometry_hint)), {"first": first, "second": second}[layer_id]
        )[1],
        proximity_geometry=lambda distance_m: f"buffered:{distance_m}",
    )

    BetweenOp().run(step, ctx)

    assert calls == [
        ("first", "buffered:250.0"),
        ("second", "buffered:250.0"),
    ]
