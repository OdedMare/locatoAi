import json
from unittest.mock import Mock

import geopandas as gpd
import pytest
from shapely.geometry import Point, box

from app.bl.executor.engine.plan_executor import PlanExecutor
from app.bl.plan.models.geo_query_plan import GeoQueryPlan
from app.bl.ports.layer_meta import LayerMeta
from app.bl.ports.layer_schema import LayerSchema
from app.common.errors.execution_error import ExecutionError
from tests.conftest import FIXTURES_DIR

# Central Tel Aviv box: 7 of the 12 schools fall inside.
CENTRAL_TLV = box(34.76, 32.06, 34.79, 32.09)


def load_fixture_plan(name: str) -> GeoQueryPlan:
    path = FIXTURES_DIR / "plans" / f"{name}.json"
    return GeoQueryPlan.model_validate(json.loads(path.read_text()))


def run_steps(executor, steps, output, **kwargs):
    plan = GeoQueryPlan(explanation="t", steps=steps, output=output)
    return executor.execute(plan, **kwargs)


def test_load_returns_all_features(executor):
    result = run_steps(executor, [{"id": "s1", "op": "load", "layer": "schools"}], "s1")
    assert len(result) == 12


def test_load_missing_data_file_returns_empty(executor):
    result = run_steps(
        executor, [{"id": "s1", "op": "load", "layer": "empty-layer"}], "s1"
    )
    assert result.empty


def test_attribute_filter_eq(executor):
    result = run_steps(executor, [
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "attribute_filter", "input": "s1",
         "field": "city_en", "operator": "eq", "value": "Tel Aviv"},
    ], "s2")
    assert len(result) == 8
    assert set(result["city_en"]) == {"Tel Aviv"}


def test_attribute_filter_contains_hebrew(executor):
    result = run_steps(executor, [
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "attribute_filter", "input": "s1",
         "field": "name", "operator": "contains", "value": "חולון"},
    ], "s2")
    assert len(result) == 2


def test_attribute_filter_contains_ignores_niqqud_and_punctuation(executor):
    """Normalization is applied before "contains" — a query written with
    niqqud/gershayim still matches plain stored text (and vice versa)."""
    result = run_steps(executor, [
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "attribute_filter", "input": "s1",
         "field": "name", "operator": "contains", "value": "עירוני ד׳"},
    ], "s2")
    assert list(result["name"]) == ["עירוני ד'"]


def test_attribute_filter_fuzzy_contains_tolerates_a_typo(executor):
    """A one-letter typo (ץ→ס) still matches via fuzzy_contains, but not
    via the exact "contains" operator — proves the two are distinct."""
    typo_query = "בית ספר גרס"  # real name: בית ספר גרץ

    fuzzy = run_steps(executor, [
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "attribute_filter", "input": "s1",
         "field": "name", "operator": "fuzzy_contains", "value": typo_query},
    ], "s2")
    assert "בית ספר גרץ" in list(fuzzy["name"])

    exact = run_steps(executor, [
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "attribute_filter", "input": "s1",
         "field": "name", "operator": "contains", "value": typo_query},
    ], "s2")
    assert exact.empty


def test_attribute_filter_fuzzy_contains_rejects_unrelated_text(executor):
    result = run_steps(executor, [
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "attribute_filter", "input": "s1",
         "field": "name", "operator": "fuzzy_contains", "value": "מקום שלא קיים בכלל"},
    ], "s2")
    assert result.empty


def test_within_geometry(executor):
    result = run_steps(executor, [
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "within_geometry", "input": "s1"},
    ], "s2", user_geometry=CENTRAL_TLV)
    assert len(result) == 7


def test_within_geometry_reprojects_non_wgs84_features():
    """A provider returning features in a metric CRS must still intersect
    correctly against user_geometry (always WGS84) — regression test for
    within_geometry silently comparing degrees against meters."""
    from app.bl.executor.ops.within_geometry import WithinGeometryOp
    from app.bl.plan.models.within_geometry_step import WithinGeometryStep
    from app.common.geo import ISRAEL_TM
    import geopandas as gpd
    from shapely.geometry import Point

    # Two points inside CENTRAL_TLV, one outside — built directly in WGS84
    # then reprojected, so the op must convert back to compare correctly.
    gdf = gpd.GeoDataFrame(
        {"name": ["in1", "in2", "out"]},
        geometry=[Point(34.77, 32.07), Point(34.78, 32.08), Point(35.5, 33.0)],
        crs="EPSG:4326",
    ).to_crs(ISRAEL_TM)

    class FakeCtx:
        user_geometry = CENTRAL_TLV
        results = {"s1": gdf}

    op = WithinGeometryOp()
    step = WithinGeometryStep(id="s2", op="within_geometry", input="s1")
    result = op.run(step, FakeCtx())
    assert set(result["name"]) == {"in1", "in2"}


def test_load_pushes_down_user_geometry_to_provider(executor, providers):
    """load must forward the request's user_geometry to the provider as a
    pushdown hint — regression test for fetching the whole layer and only
    filtering client-side via within_geometry afterwards."""
    from tests.mock_gis_provider import MockGisProvider

    real_provider: MockGisProvider = providers.get("arcgis")
    calls = []
    original = real_provider.fetch_features

    def spy_fetch_features(layer, now=None, geometry=None):
        calls.append(geometry)
        return original(layer, now=now, geometry=geometry)

    real_provider.fetch_features = spy_fetch_features
    try:
        run_steps(
            executor, [{"id": "s1", "op": "load", "layer": "schools"}], "s1",
            user_geometry=CENTRAL_TLV,
        )
    finally:
        del real_provider.fetch_features

    assert calls == [CENTRAL_TLV]


def test_load_without_request_geometry_does_not_push_down(executor, providers):
    """No boundaries on the request → load must not invent a geometry filter."""
    from tests.mock_gis_provider import MockGisProvider

    real_provider: MockGisProvider = providers.get("arcgis")
    calls = []
    original = real_provider.fetch_features

    def spy_fetch_features(layer, now=None, geometry=None):
        calls.append(geometry)
        return original(layer, now=now, geometry=geometry)

    real_provider.fetch_features = spy_fetch_features
    try:
        run_steps(executor, [{"id": "s1", "op": "load", "layer": "schools"}], "s1")
    finally:
        del real_provider.fetch_features

    assert calls == [None]


def test_near_target_layer_uses_distance_expanded_geometry(executor, providers):
    """near needs only targets inside the request boundary plus distance."""
    from tests.mock_gis_provider import MockGisProvider

    real_provider: MockGisProvider = providers.get("arcgis")
    calls = {}
    original = real_provider.fetch_features

    def spy_fetch_features(layer, now=None, geometry=None):
        calls[layer.id] = geometry
        return original(layer, now=now, geometry=geometry)

    real_provider.fetch_features = spy_fetch_features
    try:
        run_steps(executor, [
            {"id": "s1", "op": "load", "layer": "schools"},
            {"id": "s2", "op": "near", "input": "s1",
             "target_layer": "roundabouts", "distance_m": 300},
        ], "s2", user_geometry=CENTRAL_TLV)
    finally:
        del real_provider.fetch_features

    assert calls["schools"] == CENTRAL_TLV
    assert calls["roundabouts"].covers(CENTRAL_TLV)
    assert calls["roundabouts"] != CENTRAL_TLV


def test_nearest_target_layer_is_scoped_to_request_polygon(executor, providers):
    """Every layer load must carry the request polygon to its provider."""
    from tests.mock_gis_provider import MockGisProvider

    real_provider: MockGisProvider = providers.get("arcgis")
    calls = {}
    original = real_provider.fetch_features

    def spy_fetch_features(layer, now=None, geometry=None):
        calls[layer.id] = geometry
        return original(layer, now=now, geometry=geometry)

    real_provider.fetch_features = spy_fetch_features
    try:
        run_steps(executor, [
            {"id": "s1", "op": "load", "layer": "schools"},
            {"id": "s2", "op": "nearest_n", "input": "s1",
             "target_layer": "roundabouts", "count": 2},
        ], "s2", user_geometry=CENTRAL_TLV)
    finally:
        del real_provider.fetch_features

    assert calls == {"schools": CENTRAL_TLV, "roundabouts": CENTRAL_TLV}


def test_cluster_finds_group_of_close_features(executor):
    """חולון schools (שרת/קציר) are ~400m apart, isolated from the rest of
    the layer by several km — a clean 2-member cluster with a generous
    radius, small enough that nothing else joins in."""
    result = run_steps(executor, [
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "cluster", "input": "s1",
         "min_group_size": 2, "max_distance_m": 1000},
    ], "s2")
    holon = result[result["name"].isin({"בית ספר שרת חולון", "בית ספר קציר חולון"})]
    assert set(holon["name"]) == {"בית ספר שרת חולון", "בית ספר קציר חולון"}
    assert holon["cluster_id"].nunique() == 1


def test_cluster_below_min_group_size_excludes_that_group(executor):
    """The two-member Holon group is excluded when three are required;
    independent larger groups may still qualify."""
    result = run_steps(executor, [
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "cluster", "input": "s1",
         "min_group_size": 3, "max_distance_m": 1000},
    ], "s2")
    assert not set(result["name"]) & {"בית ספר שרת חולון", "בית ספר קציר חולון"}
    assert "cluster_id" in result.columns


def test_cluster_multiple_groups_get_distinct_ids(executor):
    """A radius wide enough to also pull in the central-Tel-Aviv schools
    as their own separate group — two clusters, two distinct ids, and the
    isolated Ramat Aviv school (עירוני א') stays out of both."""
    result = run_steps(executor, [
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "cluster", "input": "s1",
         "min_group_size": 2, "max_distance_m": 1000},
    ], "s2")
    assert "עירוני א' רמת אביב" not in set(result["name"])
    assert "בית ספר יהלום" in set(result["name"])  # clusters with תיכון בליך
    assert result["cluster_id"].nunique() >= 2


def test_cluster_fewer_input_rows_than_min_group_size(executor):
    result = run_steps(executor, [
        {"id": "s1", "op": "load", "layer": "roundabouts"},
        {"id": "s2", "op": "attribute_filter", "input": "s1",
         "field": "name", "operator": "contains", "value": "לא-קיים"},
        {"id": "s3", "op": "cluster", "input": "s2",
         "min_group_size": 5, "max_distance_m": 500},
    ], "s3")
    assert result.empty


def test_near_uses_meters_not_degrees(executor):
    """Schools within 300m of a square — geodesically correct set."""
    result = run_steps(executor, [
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "near", "input": "s1",
         "target_layer": "roundabouts", "distance_m": 300},
    ], "s2")
    assert set(result["name"]) == {
        "בית ספר גרץ",          # ~210m from כיכר רבין
        "בית ספר דיזנגוף",      # ~110m from כיכר דיזנגוף
        "עירוני ד'",            # ~175m from כיכר המדינה
        "אליאנס תל אביב",       # ~225m from כיכר הבימה
    }


def test_near_keeps_distance_to_nearest_target(executor):
    """near computes and keeps distance_to_target_m — not thrown away."""
    result = run_steps(executor, [
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "near", "input": "s1",
         "target_layer": "roundabouts", "distance_m": 300},
    ], "s2")
    assert "distance_to_target_m" in result.columns
    distances = result.set_index("name")["distance_to_target_m"]
    assert (distances > 0).all()
    assert (distances <= 300).all()
    # nearest of possibly-several targets, not the first join match:
    # דיזנגוף is documented ~110m from its nearest square.
    assert distances["בית ספר דיזנגוף"] == pytest.approx(110, abs=15)


def test_near_returns_match_reason_and_reference_entity(executor):
    result = run_steps(executor, [
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "near", "input": "s1",
         "target_layer": "roundabouts", "distance_m": 300},
    ], "s2")

    row = result.set_index("name").loc["בית ספר דיזנגוף"]
    assert "300" in row["match_reason"]
    target = row["nearest_target_feature"]
    assert target["type"] == "Feature"
    assert target["geometry"]["type"] == "Point"
    assert target["properties"]["name"] == "כיכר דיזנגוף"


def test_near_can_target_one_named_reference_entity(executor):
    result = run_steps(executor, [
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "near", "input": "s1",
         "target_layer": "roundabouts", "distance_m": 300,
         "target_field": "name", "target_operator": "contains",
         "target_value": "דיזנגוף"},
    ], "s2")

    assert set(result["name"]) == {"בית ספר דיזנגוף"}
    assert all(
        feature["properties"]["name"] == "כיכר דיזנגוף"
        for feature in result["nearest_target_feature"]
    )


def test_near_empty_input_has_distance_column(executor):
    """Empty results still carry the column (schema stays consistent)."""
    result = run_steps(executor, [
        {"id": "s1", "op": "load", "layer": "empty-layer"},
        {"id": "s2", "op": "near", "input": "s1",
         "target_layer": "roundabouts", "distance_m": 300},
    ], "s2")
    assert result.empty
    assert "distance_to_target_m" in result.columns


def test_nearest_n_exact_count(executor):
    """The 4 globally nearest schools to any roundabout — same set as the
    300m threshold test, since those happen to be the 4 closest overall."""
    result = run_steps(executor, [
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "nearest_n", "input": "s1",
         "target_layer": "roundabouts", "count": 4},
    ], "s2")
    assert len(result) == 4
    assert set(result["name"]) == {
        "בית ספר גרץ", "בית ספר דיזנגוף", "עירוני ד'", "אליאנס תל אביב",
    }


def test_nearest_n_count_exceeds_available(executor):
    """count > available rows degrades gracefully — all 12 schools, no error."""
    result = run_steps(executor, [
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "nearest_n", "input": "s1",
         "target_layer": "roundabouts", "count": 50},
    ], "s2")
    assert len(result) == 12


def test_nearest_n_empty_input(executor):
    result = run_steps(executor, [
        {"id": "s1", "op": "load", "layer": "empty-layer"},
        {"id": "s2", "op": "nearest_n", "input": "s1",
         "target_layer": "roundabouts", "count": 3},
    ], "s2")
    assert result.empty
    assert "distance_to_target_m" in result.columns


def test_nearest_n_empty_target(executor):
    result = run_steps(executor, [
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "nearest_n", "input": "s1",
         "target_layer": "empty-layer", "count": 3},
    ], "s2")
    assert result.empty
    assert "distance_to_target_m" in result.columns


def test_nearest_n_distance_column_present_and_sorted(executor):
    result = run_steps(executor, [
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "nearest_n", "input": "s1",
         "target_layer": "roundabouts", "count": 4},
    ], "s2")
    distances = list(result["distance_to_target_m"])
    assert distances == sorted(distances)
    assert result["match_reason"].str.contains("הקרובות ביותר").all()
    assert result["nearest_target_feature"].map(
        lambda feature: feature["type"] == "Feature"
    ).all()


def test_nearest_n_can_target_one_named_reference_entity(executor):
    result = run_steps(executor, [
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "nearest_n", "input": "s1",
         "target_layer": "roundabouts", "count": 2,
         "target_field": "name", "target_operator": "contains",
         "target_value": "דיזנגוף"},
    ], "s2")
    assert len(result) == 2
    assert all(
        feature["properties"]["name"] == "כיכר דיזנגוף"
        for feature in result["nearest_target_feature"]
    )


def test_count_of_simple_load(executor):
    result = run_steps(
        executor,
        [{"id": "s1", "op": "load", "layer": "schools"},
         {"id": "s2", "op": "count", "input": "s1"}],
        "s2",
    )
    assert result == 12
    assert isinstance(result, int)


def test_count_after_near_chain(executor):
    result = run_steps(executor, [
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "near", "input": "s1",
         "target_layer": "roundabouts", "distance_m": 300},
        {"id": "s3", "op": "count", "input": "s2"},
    ], "s3")
    assert result == 4


def test_detailed_count_releases_the_counted_geometries(executor):
    plan = GeoQueryPlan(explanation="t", steps=[
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "attribute_filter", "input": "s1",
         "field": "city_en", "operator": "eq", "value": "Tel Aviv"},
        {"id": "s3", "op": "count", "input": "s2"},
    ], output="s3")

    result = executor.execute_detailed(plan)

    assert result.scalar_result == 8
    assert result.features is None
    assert [trace["operation"] for trace in result.step_traces] == [
        "load", "attribute_filter", "count"
    ]
    assert result.step_traces[1]["input_count"] == 12
    assert result.step_traces[1]["output_count"] == 8
    assert result.step_traces[-1]["output_count"] == 8


def test_count_after_attribute_filter(executor):
    result = run_steps(executor, [
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "attribute_filter", "input": "s1",
         "field": "city_en", "operator": "eq", "value": "Tel Aviv"},
        {"id": "s3", "op": "count", "input": "s2"},
    ], "s3")
    assert result == 8


def test_count_of_empty_result(executor):
    result = run_steps(
        executor,
        [{"id": "s1", "op": "load", "layer": "empty-layer"},
         {"id": "s2", "op": "count", "input": "s1"}],
        "s2",
    )
    assert result == 0


def test_directional_northernmost(executor):
    result = run_steps(executor, [
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "directional", "input": "s1",
         "direction": "north", "count": 1},
    ], "s2")
    assert list(result["name"]) == ["עירוני א' רמת אביב"]


def test_temporal_filter_yesterday(executor, frozen_now):
    """now frozen at 2026-07-09 12:00Z → 'yesterday' = Jul 8."""
    result = run_steps(executor, [
        {"id": "s1", "op": "load", "layer": "accidents"},
        {"id": "s2", "op": "temporal_filter", "input": "s1",
         "from": "2026-07-08T00:00:00Z", "to": "2026-07-08T23:59:59Z"},
    ], "s2", now=frozen_now)
    # offsets -20, -26, -30 (Ayalon) and -22, -28 (Highway 6) land on Jul 8
    assert len(result) == 5


@pytest.mark.parametrize("provider_name", ["cubes", "tyche"])
def test_temporal_range_pushdown_reaches_temporal_providers(
    frozen_now, provider_name,
):
    cube_layer = LayerMeta(
        id="moving", name="moving", provider=provider_name,
        source_url=("cubes://db/moving" if provider_name == "cubes"
                    else "tyche://ourforces"),
    )
    catalog, providers, cubes = Mock(), Mock(), Mock()
    catalog.get_layer.return_value = cube_layer
    catalog.get_schema.return_value = LayerSchema(
        layer_id="moving", geometry_type="Point", fields=[],
        temporal_field="eventTime")
    providers.get.return_value = cubes
    cubes.fetch_features.return_value = gpd.GeoDataFrame(
        {"eventTime": ["2026-07-08T12:00:00Z"]},
        geometry=[Point(34.78, 32.08)], crs="EPSG:4326")
    time_range = ("2026-07-08T00:00:00Z", "2026-07-08T23:59:59Z")
    result = run_steps(PlanExecutor(catalog, providers), [
        {"id": "s1", "op": "load", "layer": "moving"},
        {"id": "s2", "op": "temporal_filter", "input": "s1",
         "from": time_range[0], "to": time_range[1]},
    ], "s2", now=frozen_now)

    assert len(result) == 1
    assert cubes.fetch_features.call_args.kwargs["temporal_range"] == time_range


def test_temporal_filter_uses_schema_declared_field(executor, frozen_now):
    """temporal_field comes from the provider's schema, not a hardcoded
    'timestamp' literal (accidents' mock schema declares "timestamp")."""
    schema = executor._catalog.get_schema("accidents")
    assert schema.temporal_field == "timestamp"


def test_temporal_filter_on_non_temporal_layer_raises(executor, frozen_now):
    """schools has no temporal_field — a clean ExecutionError, not a KeyError."""
    with pytest.raises(ExecutionError, match="no temporal field"):
        run_steps(executor, [
            {"id": "s1", "op": "load", "layer": "schools"},
            {"id": "s2", "op": "temporal_filter", "input": "s1",
             "from": "2026-07-08T00:00:00Z", "to": "2026-07-08T23:59:59Z"},
        ], "s2", now=frozen_now)


def test_golden_plan_yesterday_ayalon(executor, frozen_now):
    plan = load_fixture_plan("yesterday_ayalon_accidents")
    result = executor.execute(plan, now=frozen_now)
    assert len(result) == 3
    assert set(result["road_en"]) == {"Ayalon"}


def test_golden_plan_chained_near_directional(executor):
    plan = load_fixture_plan("northernmost_school_near_square")
    result = executor.execute(plan)
    # Northernmost of the 4 near-square schools is עירוני ד' (32.0871)
    assert list(result["name"]) == ["עירוני ד'"]
