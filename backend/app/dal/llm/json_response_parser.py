"""Extract a JSON object from an LLM response."""

import json
import re


def extract_json(text: str) -> dict:
    cleaned = _strip_fence(text.strip())
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        parsed = _embedded_object(cleaned)
    if not isinstance(parsed, dict):
        raise json.JSONDecodeError("Expected a JSON object", cleaned, 0)
    return parsed


def _strip_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    text = re.sub(r"^```[A-Za-z]*\s*", "", text)
    return re.sub(r"```\s*$", "", text).strip()


def _embedded_object(text: str):
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise json.JSONDecodeError("No JSON object found", text, 0)
    return json.loads(text[start:end + 1])
