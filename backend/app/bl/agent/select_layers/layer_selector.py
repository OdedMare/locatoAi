"""Agent call 1: layer selection.

Input: user query + the catalog (name/description/tags only — provider
metadata is untrusted, so it is sanitized and truncated before entering
the prompt). Output: the chosen LayerMeta objects, or a clarify question.
"""

import re
from pathlib import Path
from typing import List

from app.bl.agent.select_layers.layer_selection import LayerSelection
from app.bl.catalog.catalog_service import CatalogService
from app.bl.ports.layer_meta import LayerMeta
from app.bl.ports.llm_client import LLMClient

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "select_layers.md"

# Clarify questions are ALWAYS Hebrew (product decision, see prompt).
_FALLBACK_CLARIFY = "לא הצלחתי להתאים שכבת מידע לבקשה — אפשר לנסח מחדש?"

# Locked decision: provider/catalog text is untrusted input for prompts.
_MAX_DESCRIPTION_CHARS = 200
_MAX_NAME_CHARS = 80


def _sanitize(text: str, limit: int) -> str:
    return re.sub(r"\s+", " ", text or "").strip()[:limit]


class LayerSelector:
    def __init__(self, llm: LLMClient, catalog: CatalogService):
        self._llm = llm
        self._catalog = catalog
        self._template = _PROMPT_PATH.read_text(encoding="utf-8")

    def select(self, query: str) -> LayerSelection:
        layers = self._catalog.list_layers()
        system = self._template.replace("{catalog}", self._format_catalog(layers))

        data = self._llm.complete_json(system=system, user=query.strip())
        usage = data.get("_usage")
        if not isinstance(usage, dict):
            usage = None

        reasoning = data.get("reasoning")
        if not isinstance(reasoning, str):
            reasoning = ""
        reasoning = reasoning.strip()

        raw_ids = data.get("layer_ids") or []
        if not isinstance(raw_ids, list):
            raw_ids = []
        by_id = {layer.id: layer for layer in layers}
        # dedupe while preserving order; drop hallucinated ids
        picked = [by_id[i] for i in dict.fromkeys(raw_ids) if i in by_id]

        if picked:
            return LayerSelection(
                layers=picked, reasoning=reasoning, token_usage=usage
            )

        clarify = data.get("clarify")
        if not isinstance(clarify, str) or not clarify.strip():
            clarify = _FALLBACK_CLARIFY
        return LayerSelection(
            clarify=clarify.strip(), reasoning=reasoning, token_usage=usage
        )

    @staticmethod
    def _format_catalog(layers: List[LayerMeta]) -> str:
        lines = []
        for layer in layers:
            lines.append(
                "- id: {id} | name: {name} | tags: {tags} | description: {desc}".format(
                    id=layer.id,
                    name=_sanitize(layer.name, _MAX_NAME_CHARS),
                    tags=",".join(layer.tags[:10]),
                    desc=_sanitize(layer.description, _MAX_DESCRIPTION_CHARS),
                )
            )
        return "\n".join(lines)
