import pytest
from pydantic import ValidationError

from app.bl.plan.models.geo_query_plan import GeoQueryPlan
from app.bl.plan.validators import validate_plan
from app.common.errors.plan_validation_error import PlanValidationError

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


@pytest.mark.parametrize("op", ["crosses", "touches", "contains"])
def test_topological_relation_plan_parses(op):
    plan = make_plan(steps=[
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": op, "input": "s1", "target_layer": "roundabouts"},
    ], output="s2")
    validate_plan(plan, KNOWN_LAYERS, has_user_geometry=False)


def test_between_plan_parses():
    plan = make_plan(steps=[
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "between", "input": "s1",
         "first_target_layer": "roundabouts",
         "second_target_layer": "accidents", "corridor_width_m": 200},
    ], output="s2")
    validate_plan(plan, KNOWN_LAYERS, has_user_geometry=False)


def test_near_all_plan_parses_and_validates_all_targets():
    plan = make_plan(steps=[
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "near_all", "input": "s1",
         "targets": [{"layer": "roundabouts"}, {"layer": "accidents"}],
         "distance_m": 300, "count": 2},
    ], output="s2")
    validate_plan(plan, KNOWN_LAYERS, has_user_geometry=False)


def test_near_all_rejects_partial_target_filter():
    plan = make_plan(steps=[
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "near_all", "input": "s1",
         "targets": [
             {"layer": "roundabouts", "field": "name"},
             {"layer": "accidents"},
         ], "distance_m": 300},
    ], output="s2")
    with pytest.raises(PlanValidationError, match="supplied together"):
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


def test_moving_entity_steps_parse():
    plan = make_plan(steps=[
        {"id": "s1", "op": "load", "layer": "accidents"},
        {"id": "s2", "op": "movement_direction", "input": "s1",
         "direction": "south", "entity_field": "netId",
         "time_field": "eventTime", "min_distance_m": 100},
        {"id": "s3", "op": "latest_per_entity", "input": "s2"},
    ], output="s3")
    validate_plan(plan, KNOWN_LAYERS, has_user_geometry=False)


def test_movement_without_compass_direction_parses():
    plan = make_plan(steps=[
        {"id": "s1", "op": "load", "layer": "accidents"},
        {"id": "s2", "op": "movement_direction", "input": "s1",
         "direction": "any", "entity_field": "netId",
         "time_field": "eventTime", "min_distance_m": 50},
    ], output="s2")
    validate_plan(plan, KNOWN_LAYERS, has_user_geometry=False)


def test_trajectory_relation_and_origin_movement_parse_with_schema_fields():
    plan = make_plan(steps=[
        {"id": "s1", "op": "load", "layer": "accidents"},
        {
            "id": "s2", "op": "trajectory_relation", "input": "s1",
            "relation": "same_time", "entity_field": "personKey",
            "time_field": "observedAt", "time_tolerance_minutes": 10,
        },
        {
            "id": "s3", "op": "origin_movement", "input": "s2",
            "pattern": "departed", "start_at": "2026-07-15T20:00:00Z",
            "end_at": "2026-07-16T05:00:00Z",
            "entity_field": "personKey", "time_field": "observedAt",
        },
    ], output="s3")

    validate_plan(plan, KNOWN_LAYERS, has_user_geometry=False)


@pytest.mark.parametrize("op", ["trajectory_relation", "origin_movement"])
def test_new_trajectory_operations_require_schema_identity_and_time_fields(op):
    values = {"id": "s2", "op": op, "input": "s1"}
    if op == "trajectory_relation":
        values["relation"] = "together"
    else:
        values.update({
            "pattern": "departed",
            "start_at": "2026-07-15T20:00:00Z",
            "end_at": "2026-07-16T05:00:00Z",
        })
    with pytest.raises(ValidationError):
        make_plan(steps=[
            {"id": "s1", "op": "load", "layer": "accidents"},
            values,
        ], output="s2")


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


def test_boundaries_require_within_geometry_step():
    plan = make_plan()
    with pytest.raises(PlanValidationError, match="must apply within_geometry"):
        validate_plan(plan, KNOWN_LAYERS, has_user_geometry=True)


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


def test_proximity_target_filter_must_be_complete():
    plan = make_plan(steps=[
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "near", "input": "s1",
         "target_layer": "roundabouts", "distance_m": 300,
         "target_field": "name"},
    ], output="s2")
    with pytest.raises(PlanValidationError, match="must be supplied together"):
        validate_plan(plan, KNOWN_LAYERS, has_user_geometry=False)


def test_output_must_be_final_step():
    plan = make_plan(steps=[
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "attribute_filter", "input": "s1",
         "field": "city_en", "operator": "eq", "value": "Tel Aviv"},
    ], output="s1")
    with pytest.raises(PlanValidationError, match="must be the final step"):
        validate_plan(plan, KNOWN_LAYERS, has_user_geometry=False)


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
