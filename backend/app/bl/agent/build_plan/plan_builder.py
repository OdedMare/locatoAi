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
from typing import Callable, Dict, List, Set

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
_DIET_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "build_plan_diet.md"
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
_DIET_SAMPLE_LIMIT = 8
_DIET_MAX_SAMPLE_CHARS = 24
_DIET_MAX_ERROR_CHARS = 300
_DIET_MAX_PREVIOUS_PLAN_CHARS = 800


class PlanBuilder:
    def __init__(
        self, llm: LLMClient, catalog: CatalogService,
        diet_mode: Callable[[], bool] = lambda: False,
    ):
        self._llm = llm
        self._catalog = catalog
        self._template = _PROMPT_PATH.read_text(encoding="utf-8")
        self._diet_template = _DIET_PROMPT_PATH.read_text(encoding="utf-8")
        self._diet_mode = diet_mode

    def build(
        self,
        query: str,
        layers: List[LayerMeta],
        has_boundaries: bool,
        now: datetime,
    ) -> PlanBuildResult:
        diet = self._diet_mode()
        template = self._diet_template if diet else self._template
        system = (
            template.replace("{now}", now.isoformat())
            .replace("{has_boundaries}", "yes" if has_boundaries else "no")
            .replace("{layers}", self._format_layers(layers, diet=diet))
        )
        selected_ids = {layer.id for layer in layers}

        user = query.strip()
        usage = UsageAccumulator()
        tool_notes: List[str] = []
        tool_calls: List[Dict[str, str]] = []
        diagnostics: List[dict] = []
        attempt = 0
        while attempt < _MAX_ATTEMPTS:
            data = self._llm.complete_json(system=system, user=user)
            usage.add(data.pop(_USAGE_KEY, None))

            if data.get("tool") == _TOOL_NAME and len(tool_calls) < _MAX_TOOL_ROUNDS:
                diagnostics.append(self._diagnostic(data, "tool_requested", attempt + 1))
                tool_notes.append(self._run_sample_tool(
                    data, selected_ids, tool_calls, diet=diet
                ))
                user = self._with_tool_notes(query, tool_notes)
                continue  # a tool round does not consume the validation retry

            attempt += 1
            clarify = data.get("clarify")
            if isinstance(clarify, str) and clarify.strip() and not data.get("steps"):
                diagnostics.append(self._diagnostic(data, "clarify", attempt))
                return PlanBuildResult(
                    clarify=clarify.strip(), attempts=attempt,
                    token_usage=usage.total, tool_calls=tool_calls,
                    diagnostics=diagnostics,
                )

            try:
                plan = GeoQueryPlan.model_validate(data)
                validate_plan(plan, selected_ids, has_user_geometry=has_boundaries)
                diagnostics.append(self._diagnostic(data, "accepted", attempt))
                return PlanBuildResult(
                    plan=plan, attempts=attempt,
                    token_usage=usage.total, tool_calls=tool_calls,
                    diagnostics=diagnostics,
                )
            except (ValidationError, PlanValidationError) as exc:
                diagnostics.append(self._diagnostic(data, "rejected", attempt, exc))
                user = self._correction_message(
                    query, data, exc, tool_notes, diet=diet
                )

        return PlanBuildResult(
            clarify=_FALLBACK_CLARIFY, attempts=_MAX_ATTEMPTS,
            token_usage=usage.total, tool_calls=tool_calls,
            diagnostics=diagnostics,
        )

    @staticmethod
    def _diagnostic(data: dict, status: str, attempt: int,
                    error: Exception = None) -> dict:
        diagnostic = {"attempt": attempt, "status": status, "model_output": data}
        if error is not None:
            diagnostic.update({
                "error_type": type(error).__name__, "error": str(error),
            })
        return diagnostic

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
        diet: bool = False,
    ) -> str:
        """Execute one sample_field round; always returns a note for the
        next prompt (values or a "no values" line — never an exception,
        the model must be able to continue)."""
        layer_id = str(data.get("layer_id") or "").strip()
        field_name = str(data.get("field") or "").strip()
        tool_calls.append({"layer_id": layer_id, "field": field_name})
        values: List[str] = []
        sample_limit = _DIET_SAMPLE_LIMIT if diet else _SAMPLE_LIMIT
        sample_chars = _DIET_MAX_SAMPLE_CHARS if diet else _MAX_SAMPLE_CHARS
        if layer_id in selected_ids and field_name:
            try:
                values = self._catalog.sample_field(
                    layer_id, field_name, limit=sample_limit
                )
            except Exception:
                values = []  # sampling is best-effort; the note says so
        if not values:
            return f"No values available for layer {layer_id} field {field_name}."
        rendered = json.dumps(
            [str(v)[:sample_chars] for v in values[:sample_limit]],
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
        query: str, data: dict, error: Exception, tool_notes: List[str],
        diet: bool = False,
    ) -> str:
        error_chars = _DIET_MAX_ERROR_CHARS if diet else _MAX_ERROR_CHARS
        plan_chars = _DIET_MAX_PREVIOUS_PLAN_CHARS if diet else 1500
        notes = ("\n" + "\n".join(tool_notes)) if tool_notes else ""
        return (
            query.strip()
            + notes
            + "\n\nYour previous plan was REJECTED: "
            + str(error)[:error_chars]
            + "\nPrevious plan: "
            + json.dumps(data, ensure_ascii=False)[:plan_chars]
            + "\nReturn a corrected plan as JSON only."
        )

    def _format_layers(self, layers: List[LayerMeta], diet: bool = False) -> str:
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
                    fields=self._format_fields(schema, diet=diet),
                )
            )
            if schema.parameters:
                lines.append("  provider parameters: " + "; ".join(
                    parameter.name + (" required" if parameter.required else " optional")
                    for parameter in schema.parameters
                ))
        return "\n".join(lines)

    @staticmethod
    def _format_fields(schema: LayerSchema, diet: bool = False) -> str:
        if not schema.fields:
            return "(unknown)"
        parts = []
        for field in schema.fields:
            text = (
                field.name + ":" + field.type
                if diet else field.name + " (" + field.type + ")"
            )
            if field.samples:
                samples = field.samples[:2] if diet else field.samples[:5]
                if diet:
                    samples = [
                        str(value)[:_DIET_MAX_SAMPLE_CHARS] for value in samples
                    ]
                    text += "=" + json.dumps(samples, ensure_ascii=False)
                else:
                    text += " samples: " + json.dumps(samples, ensure_ascii=False)
            parts.append(text)
        return "; ".join(parts)
