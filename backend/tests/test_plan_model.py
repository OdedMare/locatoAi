import pytest
from pydantic import ValidationError

from app.bl.plan.models import GeoQueryPlan
from app.bl.plan.validators import validate_plan
from app.common.errors import PlanValidationError

KNOWN_LAYERS = {"schools", "roundabouts", "accidents"}


def make_plan(**overrides) -> GeoQueryPlan:
    base = {
        "explanation": "test",
        "steps": [
            {"id": "s1", "op": "load", "layer": "schools"},
            {
                "id": "s2", "op": "attribute_filter", "input": "s1",
                "field": "city_en", "operator": "eq", "value": "Tel Aviv",
            },
        ],
        "output": "s2",
    }
    base.update(overrides)
    return GeoQueryPlan.model_validate(base)


def test_valid_plan_parses():
    plan = make_plan()
    assert [s.op for s in plan.steps] == ["load", "attribute_filter"]
    validate_plan(plan, KNOWN_LAYERS, has_user_geometry=False)


def test_temporal_filter_accepts_from_alias():
    plan = make_plan(steps=[
        {"id": "s1", "op": "load", "layer": "accidents"},
        {
            "id": "s2", "op": "temporal_filter", "input": "s1",
            "from": "2026-07-08T00:00:00Z", "to": "2026-07-09T00:00:00Z",
        },
    ])
    assert plan.steps[1].from_ == "2026-07-08T00:00:00Z"


def test_unknown_op_rejected_at_parse_time():
    with pytest.raises(ValidationError):
        make_plan(steps=[{"id": "s1", "op": "drop_table", "layer": "schools"}])


def test_near_distance_bounds():
    with pytest.raises(ValidationError):
        make_plan(steps=[
            {"id": "s1", "op": "load", "layer": "schools"},
            {"id": "s2", "op": "near", "input": "s1",
             "target_layer": "roundabouts", "distance_m": 99999},
        ])


def test_duplicate_step_ids_rejected():
    plan = make_plan(steps=[
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s1", "op": "load", "layer": "roundabouts"},
    ], output="s1")
    with pytest.raises(PlanValidationError, match="Duplicate"):
        validate_plan(plan, KNOWN_LAYERS, has_user_geometry=False)


def test_forward_input_reference_rejected():
    plan = make_plan(steps=[
        {"id": "s2", "op": "attribute_filter", "input": "s1",
         "field": "city", "operator": "eq", "value": "x"},
        {"id": "s1", "op": "load", "layer": "schools"},
    ], output="s1")
    with pytest.raises(PlanValidationError, match="earlier step"):
        validate_plan(plan, KNOWN_LAYERS, has_user_geometry=False)


def test_unknown_layer_rejected():
    plan = make_plan(steps=[{"id": "s1", "op": "load", "layer": "nope"}], output="s1")
    with pytest.raises(PlanValidationError, match="not in the catalog"):
        validate_plan(plan, KNOWN_LAYERS, has_user_geometry=False)


def test_output_must_be_a_step():
    plan = make_plan(output="missing")
    with pytest.raises(PlanValidationError, match="output"):
        validate_plan(plan, KNOWN_LAYERS, has_user_geometry=False)


def test_within_geometry_requires_boundaries():
    plan = make_plan(steps=[
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "within_geometry", "input": "s1"},
    ])
    with pytest.raises(PlanValidationError, match="boundaries"):
        validate_plan(plan, KNOWN_LAYERS, has_user_geometry=False)
    validate_plan(plan, KNOWN_LAYERS, has_user_geometry=True)  # ok with geometry


def test_empty_plan_rejected():
    plan = GeoQueryPlan(explanation="x", steps=[], output="s1")
    with pytest.raises(PlanValidationError, match="no steps"):
        validate_plan(plan, KNOWN_LAYERS, has_user_geometry=False)


def test_nearest_n_unknown_target_layer_rejected():
    plan = make_plan(steps=[
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "nearest_n", "input": "s1",
         "target_layer": "nope", "count": 3},
    ], output="s2")
    with pytest.raises(PlanValidationError, match="not in the catalog"):
        validate_plan(plan, KNOWN_LAYERS, has_user_geometry=False)


def test_nearest_n_count_bounds():
    with pytest.raises(ValidationError):
        make_plan(steps=[
            {"id": "s1", "op": "load", "layer": "schools"},
            {"id": "s2", "op": "nearest_n", "input": "s1",
             "target_layer": "roundabouts", "count": 0},
        ])
    with pytest.raises(ValidationError):
        make_plan(steps=[
            {"id": "s1", "op": "load", "layer": "schools"},
            {"id": "s2", "op": "nearest_n", "input": "s1",
             "target_layer": "roundabouts", "count": 51},
        ])


def test_count_as_output_with_nothing_downstream_is_valid():
    plan = make_plan(steps=[
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "count", "input": "s1"},
    ], output="s2")
    validate_plan(plan, KNOWN_LAYERS, has_user_geometry=False)  # does not raise


def test_count_referenced_as_input_rejected():
    plan = make_plan(steps=[
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "count", "input": "s1"},
        {"id": "s3", "op": "attribute_filter", "input": "s2",
         "field": "x", "operator": "eq", "value": "y"},
    ], output="s3")
    with pytest.raises(
        PlanValidationError, match="cannot be used as another step's input"
    ):
        validate_plan(plan, KNOWN_LAYERS, has_user_geometry=False)


def test_count_not_set_as_output_rejected():
    plan = make_plan(steps=[
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "count", "input": "s1"},
    ], output="s1")
    with pytest.raises(PlanValidationError, match="must be the final, output step"):
        validate_plan(plan, KNOWN_LAYERS, has_user_geometry=False)
