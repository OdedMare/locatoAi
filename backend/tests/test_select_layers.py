import json

import pytest

from app.bl.agent.select_layers import _FALLBACK_CLARIFY, LayerSelector
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
    assert "- id: schools | name: בתי ספר" in llm.last_system
    assert "{catalog}" not in llm.last_system
    assert llm.last_user == "schools"


def test_extract_json_plain():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_fenced():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_with_prose():
    assert extract_json('Here you go: {"a": 1} hope that helps!') == {"a": 1}


def test_extract_json_garbage_raises():
    with pytest.raises(json.JSONDecodeError):
        extract_json("no json here")
