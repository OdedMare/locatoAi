"""Agent call 2: plan building.

Input: query + the selected layers with their schemas (field names/types/
sample values — sanitized: catalog text is untrusted). Output: a validated
GeoQueryPlan, or a Hebrew clarify.

Policy (from the MVP guide): if the plan fails validation, retry ONCE with
the validation error appended to the conversation, then fall back to
clarify. Both attempts are visible in `attempts`.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import ValidationError

from app.bl.catalog.catalog_service import CatalogService
from app.bl.plan.models import GeoQueryPlan
from app.bl.plan.validators import validate_plan
from app.bl.ports import LayerMeta, LayerSchema, LLMClient
from app.common.errors import PlanValidationError

_PROMPT_PATH = Path(__file__).parent / "prompts" / "build_plan.md"

# Clarify is ALWAYS Hebrew (product decision, same as selection).
_FALLBACK_CLARIFY = "לא הצלחתי לבנות שאילתה מהבקשה — אפשר לנסח אותה אחרת?"

_MAX_ATTEMPTS = 2  # one build + one correction with the error appended
_MAX_ERROR_CHARS = 500
_USAGE_KEY = "_usage"  # attached by the LLM client, not part of the plan


@dataclass
class PlanBuildResult:
    plan: Optional[GeoQueryPlan] = None
    clarify: Optional[str] = None
    attempts: int = 0
    token_usage: Optional[Dict[str, int]] = None


class PlanBuilder:
    def __init__(self, llm: LLMClient, catalog: CatalogService):
        self._llm = llm
        self._catalog = catalog
        self._template = _PROMPT_PATH.read_text(encoding="utf-8")

    def build(
        self,
        query: str,
        layers: List[LayerMeta],
        has_boundaries: bool,
        now: datetime,
    ) -> PlanBuildResult:
        system = (
            self._template.replace("{now}", now.isoformat())
            .replace("{has_boundaries}", "yes" if has_boundaries else "no")
            .replace("{layers}", self._format_layers(layers))
        )
        selected_ids = {layer.id for layer in layers}

        user = query.strip()
        usage = _UsageAccumulator()
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            data = self._llm.complete_json(system=system, user=user)
            usage.add(data.pop(_USAGE_KEY, None))

            clarify = data.get("clarify")
            if isinstance(clarify, str) and clarify.strip() and not data.get("steps"):
                return PlanBuildResult(
                    clarify=clarify.strip(), attempts=attempt, token_usage=usage.total
                )

            try:
                plan = GeoQueryPlan.model_validate(data)
                validate_plan(plan, selected_ids, has_user_geometry=has_boundaries)
                return PlanBuildResult(
                    plan=plan, attempts=attempt, token_usage=usage.total
                )
            except (ValidationError, PlanValidationError) as exc:
                user = self._correction_message(query, data, exc)

        return PlanBuildResult(
            clarify=_FALLBACK_CLARIFY, attempts=_MAX_ATTEMPTS, token_usage=usage.total
        )

    @staticmethod
    def _correction_message(query: str, data: dict, error: Exception) -> str:
        return (
            query.strip()
            + "\n\nYour previous plan was REJECTED: "
            + str(error)[:_MAX_ERROR_CHARS]
            + "\nPrevious plan: "
            + json.dumps(data, ensure_ascii=False)[:1500]
            + "\nReturn a corrected plan as JSON only."
        )

    def _format_layers(self, layers: List[LayerMeta]) -> str:
        lines = []
        for layer in layers:
            schema = self._catalog.get_schema(layer.id)
            lines.append(
                "- id: {id} | name: {name} | geometry: {geom}\n  fields: {fields}".format(
                    id=layer.id,
                    name=layer.name,
                    geom=schema.geometry_type,
                    fields=self._format_fields(schema),
                )
            )
        return "\n".join(lines)

    @staticmethod
    def _format_fields(schema: LayerSchema) -> str:
        if not schema.fields:
            return "(unknown)"
        parts = []
        for field in schema.fields:
            text = field.name + " (" + field.type + ")"
            if field.samples:
                text += " samples: " + json.dumps(field.samples[:5], ensure_ascii=False)
            parts.append(text)
        return "; ".join(parts)


class _UsageAccumulator:
    """Sums token usage across build attempts."""

    def __init__(self) -> None:
        self.total: Optional[Dict[str, int]] = None

    def add(self, usage) -> None:
        if not isinstance(usage, dict):
            return
        if self.total is None:
            self.total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        for key in self.total:
            self.total[key] += int(usage.get(key, 0))
