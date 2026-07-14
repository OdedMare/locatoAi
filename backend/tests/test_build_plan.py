from datetime import datetime, timezone

from app.bl.agent.build_plan import _FALLBACK_CLARIFY, PlanBuilder
from app.bl.query_orchestrator import QueryOrchestrator
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

    def complete_json(self, system: str, user: str) -> dict:
        self.calls.append({"system": system, "user": user})
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


def test_orchestrator_full_flow_returns_features(catalog, executor):
    selection_response = {
        "reasoning": "בתי ספר ליד כיכרות",
        "layer_ids": ["schools", "roundabouts"],
        "clarify": None,
    }
    from app.bl.agent.select_layers import LayerSelector

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
