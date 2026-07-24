from datetime import datetime, timezone

from app.bl.agent.build_plan.geo_skill_catalog import GeoSkillCatalog
from app.bl.agent.build_plan.plan_build_result import PlanBuildResult
from app.bl.agent.build_plan.plan_builder import _FALLBACK_CLARIFY, PlanBuilder
from app.bl.agent.build_plan.preserves_constraints import preserves_constraints
from app.bl.plan.models.geo_query_plan import GeoQueryPlan
from app.bl.query_orchestrator.query_orchestrator import QueryOrchestrator
from scripts.eval_build_plan import PRESENT, check_plan
from tests.conftest import LAYERS

NOW = datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc)

SCHOOLS = next(l for l in LAYERS if l.id == "schools")
ROUNDABOUTS = next(l for l in LAYERS if l.id == "roundabouts")

VALID_PLAN = {
    "explanation": "בתי ספר ליד כיכרות",
    "steps": [
        {"id": "s1", "op": "load", "layer": "schools"},
        {"id": "s2", "op": "near", "input": "s1",
         "target_layer": "roundabouts", "distance_m": 300},
    ],
    "output": "s2",
    "context_layers": ["roundabouts"],
}

OPERATIONS = (
    "load", "within_geometry", "attribute_filter", "near", "nearest_n",
    "near_all", "cluster", "latest_per_entity", "movement_direction",
    "trajectory_relation", "origin_movement",
    "directional", "between", "crosses", "touches", "contains",
    "temporal_filter", "count",
)

BAD_PLAN_UNKNOWN_LAYER = {
    "explanation": "x",
    "steps": [{"id": "s1", "op": "load", "layer": "hallucinated-layer"}],
    "output": "s1",
}


class SequenceLLM:
    """LLMClient fake returning queued responses; records prompts."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete_json(self, system: str, user: str, schema=None) -> dict:
        self.calls.append({"system": system, "user": user, "schema": schema})
        return dict(self.responses.pop(0))


def test_valid_plan_first_attempt(catalog):
    llm = SequenceLLM([VALID_PLAN])
    result = PlanBuilder(llm, catalog).build(
        "בתי ספר ליד כיכרות", [SCHOOLS, ROUNDABOUTS], has_boundaries=False, now=NOW
    )
    assert result.plan is not None
    assert result.attempts == 1
    assert [s.op for s in result.plan.steps] == ["load", "near"]
    # prompt carries the schema with sample values
    assert "city_en" in llm.calls[0]["system"]
    assert "provider: arcgis" in llm.calls[0]["system"]
    assert "OurForce mission profile" not in llm.calls[0]["system"]


def test_diet_plan_prompt_is_short_and_preserves_all_operations(catalog):
    full_llm = SequenceLLM([VALID_PLAN])
    diet_llm = SequenceLLM([VALID_PLAN])
    args = (
        "בתי ספר ליד כיכרות", [SCHOOLS, ROUNDABOUTS], False, NOW,
    )

    PlanBuilder(full_llm, catalog).build(*args)
    result = PlanBuilder(
        diet_llm, catalog, diet_mode=lambda: True
    ).build(*args)

    assert result.plan is not None
    full_prompt = full_llm.calls[0]["system"]
    diet_prompt = diet_llm.calls[0]["system"]
    assert len(diet_prompt) < len(full_prompt)
    for operation in OPERATIONS:
        assert f'op:"{operation}"' in diet_prompt
    assert "city_en:string=" in diet_prompt
    assert "sample_field" in diet_prompt
    assert 'direction:"any"|"north"|"south"|"east"|"west"' in diet_prompt
    assert "profile:our-force" not in diet_prompt


def test_geo_skill_catalog_documents_and_renders_every_operation():
    full = GeoSkillCatalog().render()
    diet = GeoSkillCatalog().render(diet=True)

    assert full.count("**Use when:**") == len(OPERATIONS)
    assert full.count("**Do not use when:**") == len(OPERATIONS)
    for operation in OPERATIONS:
        assert f"# `{operation}`" in full
        assert f'op:"{operation}"' in full
        assert f'op:"{operation}"' in diet


def test_build_plan_eval_checks_operations_roles_and_constraints():
    result = PlanBuildResult(plan=GeoQueryPlan.model_validate(VALID_PLAN))
    case = {
        "ops": ("load", "near"),
        "subject": "בתי ספר",
        "context": ("כיכרות",),
        "checks": (("near", "distance_m", 300),),
    }

    assert check_plan(result, case, [SCHOOLS, ROUNDABOUTS])[0]
    case["checks"] = (("near", "target_field", PRESENT),)
    ok, detail = check_plan(result, case, [SCHOOLS, ROUNDABOUTS])
    assert not ok
    assert "near.target_field must be present" in detail


def test_hebrew_multi_reference_query_builds_near_all(catalog):
    plan_response = {
        "explanation": "שני בתי ספר ליד כיכר ואירוע תאונה",
        "steps": [
            {"id": "s1", "op": "load", "layer": "schools"},
            {"id": "s2", "op": "near_all", "input": "s1",
             "targets": [{"layer": "roundabouts"}, {"layer": "accidents"}],
             "distance_m": 300, "count": 2},
        ],
        "output": "s2",
        "context_layers": ["roundabouts", "accidents"],
    }
    llm = SequenceLLM([plan_response])

    result = PlanBuilder(llm, catalog).build(
        "תמצא לי את 2 בתי הספר ליד הכיכר ואיפה שהתאונה",
        [SCHOOLS, ROUNDABOUTS, next(l for l in LAYERS if l.id == "accidents")],
        has_boundaries=False,
        now=NOW,
    )

    assert result.plan is not None
    step = result.plan.steps[1]
    assert step.op == "near_all"
    assert step.count == 2
    assert [target.layer for target in step.targets] == ["roundabouts", "accidents"]
    assert "simultaneous reference" in llm.calls[0]["system"]


def test_invalid_plan_retried_with_error_then_succeeds(catalog):
    llm = SequenceLLM([BAD_PLAN_UNKNOWN_LAYER, VALID_PLAN])
    result = PlanBuilder(llm, catalog).build(
        "q", [SCHOOLS, ROUNDABOUTS], has_boundaries=False, now=NOW
    )
    assert result.plan is not None
    assert result.attempts == 2
    # the correction turn contains the validator's message
    assert "REJECTED" in llm.calls[1]["user"]
    assert "not in the catalog" in llm.calls[1]["user"]


def test_two_invalid_plans_fall_back_to_hebrew_clarify(catalog):
    llm = SequenceLLM([BAD_PLAN_UNKNOWN_LAYER, BAD_PLAN_UNKNOWN_LAYER])
    result = PlanBuilder(llm, catalog).build(
        "q", [SCHOOLS], has_boundaries=False, now=NOW
    )
    assert result.plan is None
    assert result.clarify == _FALLBACK_CLARIFY


def test_builder_clarify_passthrough(catalog):
    llm = SequenceLLM([{"clarify": "לאיזה מרחק התכוונת?"}])
    result = PlanBuilder(llm, catalog).build(
        "q", [SCHOOLS], has_boundaries=False, now=NOW
    )
    assert result.plan is None
    assert result.clarify == "לאיזה מרחק התכוונת?"


def test_within_geometry_rejected_without_boundaries_then_corrected(catalog):
    with_geometry = {
        "explanation": "x",
        "steps": [
            {"id": "s1", "op": "load", "layer": "schools"},
            {"id": "s2", "op": "within_geometry", "input": "s1"},
        ],
        "output": "s2",
    }
    llm = SequenceLLM([with_geometry, VALID_PLAN])
    result = PlanBuilder(llm, catalog).build(
        "q", [SCHOOLS, ROUNDABOUTS], has_boundaries=False, now=NOW
    )
    assert result.plan is not None
    assert result.attempts == 2


SAMPLE_TOOL_CALL = {"tool": "sample_field", "layer_id": "schools", "field": "city_en"}


def test_sample_field_tool_round_then_plan(catalog):
    llm = SequenceLLM([SAMPLE_TOOL_CALL, VALID_PLAN])
    result = PlanBuilder(llm, catalog).build(
        "q", [SCHOOLS, ROUNDABOUTS], has_boundaries=False, now=NOW
    )
    assert result.plan is not None
    assert result.attempts == 1  # the tool round does not consume an attempt
    assert result.tool_calls == [{"layer_id": "schools", "field": "city_en"}]
    # the second prompt carries the sampled values
    second_user = llm.calls[1]["user"]
    assert "Field values for layer schools field city_en" in second_user
    assert "Tel Aviv" in second_user


def test_sample_field_unknown_field_is_soft(catalog):
    llm = SequenceLLM([
        {"tool": "sample_field", "layer_id": "schools", "field": "no_such_field"},
        VALID_PLAN,
    ])
    result = PlanBuilder(llm, catalog).build(
        "q", [SCHOOLS, ROUNDABOUTS], has_boundaries=False, now=NOW
    )
    assert result.plan is not None
    assert "No values available" in llm.calls[1]["user"]


def test_sample_field_unselected_layer_gets_no_values(catalog):
    llm = SequenceLLM([
        {"tool": "sample_field", "layer_id": "accidents", "field": "road"},
        VALID_PLAN,
    ])
    result = PlanBuilder(llm, catalog).build(
        "q", [SCHOOLS, ROUNDABOUTS], has_boundaries=False, now=NOW
    )
    assert result.plan is not None
    assert "No values available" in llm.calls[1]["user"]


def test_sample_field_budget_exhausted_falls_back_to_retry_policy(catalog):
    # 3 tool rounds allowed; the 4th tool response is treated as a bad plan
    # (consumes the validation retry), the 5th still asks → fallback clarify.
    llm = SequenceLLM([SAMPLE_TOOL_CALL] * 5)
    result = PlanBuilder(llm, catalog).build(
        "q", [SCHOOLS, ROUNDABOUTS], has_boundaries=False, now=NOW
    )
    assert result.plan is None
    assert result.clarify == _FALLBACK_CLARIFY
    assert len(result.tool_calls) == 3
    assert len(llm.calls) == 5


def test_zero_result_replan_preserves_constraints(catalog):
    previous = GeoQueryPlan.model_validate(VALID_PLAN)
    revised = dict(VALID_PLAN)
    revised["explanation"] = "revised ordering"
    result = PlanBuilder(SequenceLLM([revised]), catalog).replan_after_empty(
        "q", [SCHOOLS, ROUNDABOUTS], previous, False, NOW
    )
    assert result.plan is not None


def test_zero_result_replan_rejects_wider_distance(catalog):
    previous = GeoQueryPlan.model_validate(VALID_PLAN)
    widened = {
        **VALID_PLAN,
        "steps": [VALID_PLAN["steps"][0], {**VALID_PLAN["steps"][1],
                                            "distance_m": 1000}],
    }
    result = PlanBuilder(SequenceLLM([widened]), catalog).replan_after_empty(
        "q", [SCHOOLS, ROUNDABOUTS], previous, False, NOW
    )
    assert result.plan is None
    assert "שינתה מגבלה" in result.clarify
    assert not preserves_constraints(previous, GeoQueryPlan.model_validate(widened))


def test_orchestrator_full_flow_returns_features(catalog, executor):
    selection_response = {
        "reasoning": "בתי ספר ליד כיכרות",
        "layer_ids": ["schools", "roundabouts"],
        "clarify": None,
    }
    from app.bl.agent.select_layers.layer_selector import LayerSelector

    selector = LayerSelector(SequenceLLM([selection_response]), catalog)
    builder = PlanBuilder(SequenceLLM([VALID_PLAN]), catalog)
    orchestrator = QueryOrchestrator(
        catalog, executor, layer_selector=selector, plan_builder=builder
    )

    outcome = orchestrator.run_query("בתי ספר ליד כיכרות", boundaries=None)

    assert outcome.status == "ok"
    assert outcome.plan is not None
    # the 4 schools within 300m of a square (see test_executor)
    assert len(outcome.features) == 4
    assert [l.id for l in outcome.selected_layers] == ["schools", "roundabouts"]
    assert set(outcome.timing_ms) == {"select", "plan", "execute"}
    assert [entry["stage"] for entry in outcome.pipeline_trace] == [
        "layer_selection", "plan_building", "execute_step", "execute_step",
        "response",
    ]
    assert outcome.pipeline_trace[0]["selected_layer_ids"] == [
        "schools", "roundabouts"
    ]
    assert outcome.pipeline_trace[-1]["geometry_returned"] is True
    assert outcome.pipeline_trace[-1]["feature_count"] == 4


def test_orchestrator_surfaces_clarify_after_empty_result(catalog, executor):
    selection = {
        "reasoning": "נבחרה שכבה ריקה",
        "layer_ids": ["empty-layer"],
        "clarify": None,
    }
    plan = {
        "explanation": "טעינת השכבה",
        "steps": [{"id": "load_empty", "op": "load", "layer": "empty-layer"}],
        "output": "load_empty",
        "context_layers": [],
    }
    clarify = "לא נמצאו תוצאות. האם לחפש באזור או בזמן אחר?"
    from app.bl.agent.select_layers.layer_selector import LayerSelector

    orchestrator = QueryOrchestrator(
        catalog,
        executor,
        layer_selector=LayerSelector(SequenceLLM([selection]), catalog),
        plan_builder=PlanBuilder(SequenceLLM([plan, {"clarify": clarify}]), catalog),
    )

    outcome = orchestrator.run_query("מצא משהו", boundaries=None)

    assert outcome.status == "clarify"
    assert outcome.clarify == clarify
    assert outcome.features.empty
    assert outcome.pipeline_trace[-1]["stage"] == "zero_result_diagnosis"
