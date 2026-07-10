import json

from shapely.geometry import box

from app.bl.plan.models import GeoQueryPlan
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


def test_within_geometry(executor):
    result = run_steps(executor, [
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "within_geometry", "input": "s1"},
    ], "s2", user_geometry=CENTRAL_TLV)
    assert len(result) == 7


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
