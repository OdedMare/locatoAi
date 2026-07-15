"""Agent call 2: plan building.

Input: query + the selected layers with their schemas (field names/types/
sample values — sanitized: catalog text is untrusted). Output: a validated
GeoQueryPlan, or a Hebrew clarify.

Policy (from the MVP guide): if the plan fails validation, retry ONCE with
the validation error appended to the conversation, then fall back to
clarify. Both attempts are visible in `attempts`.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set

from pydantic import ValidationError

from app.bl.agent.build_plan.plan_build_result import PlanBuildResult
from app.bl.agent.build_plan.preserves_constraints import preserves_constraints
from app.bl.agent.build_plan.usage_accumulator import UsageAccumulator
from app.bl.catalog.catalog_service import CatalogService
from app.bl.plan.models.geo_query_plan import GeoQueryPlan
from app.bl.plan.validators import validate_plan
from app.bl.ports.layer_meta import LayerMeta
from app.bl.ports.layer_schema import LayerSchema
from app.bl.ports.llm_client import LLMClient
from app.common.errors.plan_validation_error import PlanValidationError

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "build_plan.md"
logger = logging.getLogger(__name__)

# Clarify is ALWAYS Hebrew (product decision, same as selection).
_FALLBACK_CLARIFY = "לא הצלחתי לבנות שאילתה מהבקשה — אפשר לנסח אותה אחרת?"

_MAX_ATTEMPTS = 2  # one build + one correction with the error appended
_MAX_ERROR_CHARS = 500
_USAGE_KEY = "_usage"  # attached by the LLM client, not part of the plan

# The sample_field tool (see prompts/build_plan.md): the model may ask for
# extra distinct values of one field before committing to a plan. Tool
# rounds have their own budget and do not consume the validation retry.
# Bumped from 2 to 3: the clarify policy now expects the model to lean on
# this tool more habitually (self-serve field/value checks) rather than
# asking the user, so a tight cap would push it toward premature clarify.
_TOOL_NAME = "sample_field"
_MAX_TOOL_ROUNDS = 3
_SAMPLE_LIMIT = 20
_MAX_SAMPLE_CHARS = 40


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
        usage = UsageAccumulator()
        tool_notes: List[str] = []
        tool_calls: List[Dict[str, str]] = []
        attempt = 0
        while attempt < _MAX_ATTEMPTS:
            data = self._llm.complete_json(system=system, user=user)
            usage.add(data.pop(_USAGE_KEY, None))

            if data.get("tool") == _TOOL_NAME and len(tool_calls) < _MAX_TOOL_ROUNDS:
                tool_notes.append(self._run_sample_tool(data, selected_ids, tool_calls))
                user = self._with_tool_notes(query, tool_notes)
                continue  # a tool round does not consume the validation retry

            attempt += 1
            clarify = data.get("clarify")
            if isinstance(clarify, str) and clarify.strip() and not data.get("steps"):
                return PlanBuildResult(
                    clarify=clarify.strip(), attempts=attempt,
                    token_usage=usage.total, tool_calls=tool_calls,
                )

            try:
                plan = GeoQueryPlan.model_validate(data)
                validate_plan(plan, selected_ids, has_user_geometry=has_boundaries)
                return PlanBuildResult(
                    plan=plan, attempts=attempt,
                    token_usage=usage.total, tool_calls=tool_calls,
                )
            except (ValidationError, PlanValidationError) as exc:
                user = self._correction_message(query, data, exc, tool_notes)

        return PlanBuildResult(
            clarify=_FALLBACK_CLARIFY, attempts=_MAX_ATTEMPTS,
            token_usage=usage.total, tool_calls=tool_calls,
        )

    def replan_after_empty(self, query: str, layers: List[LayerMeta],
                           previous: GeoQueryPlan, has_boundaries: bool,
                           now: datetime) -> PlanBuildResult:
        diagnostic = (
            query.strip()
            + "\n\nThe validated plan below executed successfully but returned zero rows. "
            + "Diagnose field/value or operation-order mistakes using tools and return "
            + "one revised plan. Preserve every user constraint exactly; never widen "
            + "time, distance, geography, counts, targets, or movement thresholds.\n"
            + json.dumps(previous.model_dump(by_alias=True), ensure_ascii=False)
        )
        result = self.build(diagnostic, layers, has_boundaries, now)
        if result.plan is not None and not preserves_constraints(previous, result.plan):
            result.plan = None
            result.clarify = "לא נמצאו תוצאות, ותוכנית התיקון שינתה מגבלה מהבקשה."
        return result

    def _run_sample_tool(
        self,
        data: dict,
        selected_ids: Set[str],
        tool_calls: List[Dict[str, str]],
    ) -> str:
        """Execute one sample_field round; always returns a note for the
        next prompt (values or a "no values" line — never an exception,
        the model must be able to continue)."""
        layer_id = str(data.get("layer_id") or "").strip()
        field_name = str(data.get("field") or "").strip()
        tool_calls.append({"layer_id": layer_id, "field": field_name})
        values: List[str] = []
        if layer_id in selected_ids and field_name:
            try:
                values = self._catalog.sample_field(
                    layer_id, field_name, limit=_SAMPLE_LIMIT
                )
            except Exception:
                values = []  # sampling is best-effort; the note says so
        if not values:
            return f"No values available for layer {layer_id} field {field_name}."
        rendered = json.dumps(
            [str(v)[:_MAX_SAMPLE_CHARS] for v in values[:_SAMPLE_LIMIT]],
            ensure_ascii=False,
        )
        return f"Field values for layer {layer_id} field {field_name}: {rendered}"

    @staticmethod
    def _with_tool_notes(query: str, tool_notes: List[str]) -> str:
        return (
            query.strip()
            + "\n\n"
            + "\n".join(tool_notes)
            + "\nNow return the plan (or clarify) as JSON only."
        )

    @staticmethod
    def _correction_message(
        query: str, data: dict, error: Exception, tool_notes: List[str]
    ) -> str:
        notes = ("\n" + "\n".join(tool_notes)) if tool_notes else ""
        return (
            query.strip()
            + notes
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
            logger.info(
                "Plan schema layer=%s fields=%d samples=%s",
                layer.id, len(schema.fields),
                {field.name: len(field.samples) for field in schema.fields},
            )
            lines.append(
                "- id: {id} | name: {name} | geometry: {geom}\n  fields: {fields}".format(
                    id=layer.id,
                    name=layer.name,
                    geom=schema.geometry_type,
                    fields=self._format_fields(schema),
                )
            )
            if schema.parameters:
                lines.append("  provider parameters: " + "; ".join(
                    parameter.name + (" required" if parameter.required else " optional")
                    for parameter in schema.parameters
                ))
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
