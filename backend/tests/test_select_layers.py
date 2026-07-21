import json

import pytest

from app.bl.agent.select_layers.layer_selector import _FALLBACK_CLARIFY, LayerSelector
from app.dal.llm.openai_client import extract_json


class FakeLLM:
    """LLMClient port implementation returning a canned response."""

    def __init__(self, response: dict):
        self.response = response
        self.last_system = None
        self.last_user = None

    def complete_json(self, system: str, user: str) -> dict:
        self.last_system = system
        self.last_user = user
        return self.response


def test_selects_known_layers_in_order(catalog):
    llm = FakeLLM({
        "reasoning": "צריך בתי ספר וכיכרות",
        "layer_ids": ["roundabouts", "schools"],
        "clarify": None,
    })
    selection = LayerSelector(llm, catalog).select("schools near squares")
    assert [l.id for l in selection.layers] == ["roundabouts", "schools"]
    assert selection.clarify is None
    assert selection.reasoning == "צריך בתי ספר וכיכרות"


def test_hallucinated_ids_are_dropped_and_deduped(catalog):
    llm = FakeLLM({"layer_ids": ["schools", "nope-123", "schools"], "clarify": None})
    selection = LayerSelector(llm, catalog).select("schools")
    assert [l.id for l in selection.layers] == ["schools"]


def test_malformed_layer_ids_are_dropped_without_crashing(catalog):
    llm = FakeLLM({"layer_ids": [{"id": "schools"}, "roundabouts"]})
    selection = LayerSelector(llm, catalog).select("roundabouts")
    assert [layer.id for layer in selection.layers] == ["roundabouts"]
    assert selection.dropped_layer_ids == ["{'id': 'schools'}"]


def test_clarify_passthrough(catalog):
    llm = FakeLLM({"layer_ids": [], "clarify": "איזה סוג מבנים?"})
    selection = LayerSelector(llm, catalog).select("תראה לי מבנים")
    assert selection.layers == []
    assert selection.clarify == "איזה סוג מבנים?"


def test_no_ids_no_clarify_falls_back(catalog):
    llm = FakeLLM({"layer_ids": []})
    selection = LayerSelector(llm, catalog).select("gibberish")
    assert selection.clarify == _FALLBACK_CLARIFY


def test_catalog_metadata_is_sanitized_into_prompt(catalog):
    llm = FakeLLM({"layer_ids": ["schools"]})
    LayerSelector(llm, catalog).select("schools")
    assert "- id: schools | provider: arcgis | name: בתי ספר" in llm.last_system
    assert "{catalog}" not in llm.last_system
    assert llm.last_user == "schools"


def test_selector_prompt_requires_all_multi_reference_layers(catalog):
    llm = FakeLLM({
        "reasoning": "נדרשות שכבת נושא ושתי שכבות ייחוס",
        "layer_ids": ["schools", "roundabouts", "accidents"],
        "clarify": None,
    })
    selection = LayerSelector(llm, catalog).select(
        "תמצא לי 2 בתי ספר ליד הכיכר ואיפה שהתאונה"
    )

    assert [layer.id for layer in selection.layers] == [
        "schools", "roundabouts", "accidents"
    ]
    assert "Never drop the second reference layer" in llm.last_system
    assert "`tyche` כוחותינו/OurForce layer as the subject" in llm.last_system


def test_diet_selector_keeps_contract_with_shorter_prompt(catalog):
    response = {"layer_ids": ["schools"], "reasoning": "בתי ספר"}
    full_llm = FakeLLM(response)
    diet_llm = FakeLLM(response)

    LayerSelector(full_llm, catalog).select("schools")
    LayerSelector(
        diet_llm, catalog, diet_mode=lambda: True
    ).select("schools")

    assert len(diet_llm.last_system) < len(full_llm.last_system) * 0.6
    assert "schools|arcgis|בתי ספר|" in diet_llm.last_system
    assert '"layer_ids"' in diet_llm.last_system
    assert "A near B and C" in diet_llm.last_system
    assert "`tyche` כוחותינו layer as subject" in diet_llm.last_system


def test_extract_json_plain():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_fenced():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_with_prose():
    assert extract_json('Here you go: {"a": 1} hope that helps!') == {"a": 1}


def test_extract_json_garbage_raises():
    with pytest.raises(json.JSONDecodeError):
        extract_json("no json here")


def test_extract_json_array_raises_instead_of_reaching_pipeline():
    with pytest.raises(json.JSONDecodeError, match="Expected a JSON object"):
        extract_json('[{"layer_ids": ["schools"]}]')


def test_extract_model_ids_handles_all_shapes():
    from app.dal.llm.openai_client import extract_model_ids

    openai_shape = {"data": [{"id": "gpt-4o"}, {"id": "gpt-4o-mini"}]}
    gateway_shape = {"models": [{"name": "llama3"}, {"model": "qwen"}]}
    bare_list = ["m1", {"id": "m2"}]
    assert extract_model_ids(openai_shape) == ["gpt-4o", "gpt-4o-mini"]
    assert extract_model_ids(gateway_shape) == ["llama3", "qwen"]
    assert extract_model_ids(bare_list) == ["m1", "m2"]
    # the shapes that crashed before: data=None / non-list / empty
    assert extract_model_ids({"data": None}) == []
    assert extract_model_ids({"object": "list"}) == []
    assert extract_model_ids(None) == []
