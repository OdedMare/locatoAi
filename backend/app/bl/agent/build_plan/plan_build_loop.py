"""Bounded LLM/tool/validation loop for plan construction."""

import json

from pydantic import ValidationError

from app.bl.agent.build_plan.plan_build_result import PlanBuildResult
from app.bl.agent.build_plan.plan_build_state import PlanBuildState
from app.bl.plan.models.geo_query_plan import GeoQueryPlan
from app.bl.plan.validators import validate_plan
from app.common.errors.plan_validation_error import PlanValidationError


class PlanBuildLoop:
    _MAX_ATTEMPTS = 2
    _MAX_SAMPLE_ROUNDS = 3
    _MAX_SKILL_ROUNDS = 2
    _SAMPLE_TOOL = "sample_field"
    _SKILL_TOOL = "load_skill"
    _FALLBACK = "לא הצלחתי לבנות שאילתה מהבקשה — אפשר לנסח אותה אחרת?"

    def __init__(self, llm, catalog, skill_loader=None) -> None:
        self._llm = llm
        self._catalog = catalog
        self._skill_loader = skill_loader

    def run(self, query, system, selected_ids, has_boundaries, diet) -> PlanBuildResult:
        state = PlanBuildState(query)
        while state.attempt < self._MAX_ATTEMPTS:
            data = self._llm.complete_json(system=system, user=state.user)
            state.usage.add(data.pop("_usage", None))
            if self._is_tool_request(data, state):
                self._handle_tool(data, selected_ids, state, diet)
                continue
            state.attempt += 1
            result = self._result(data, state, selected_ids, has_boundaries, diet)
            if result is not None:
                return result
        return self._build_result(state, clarify=self._FALLBACK)

    def _result(self, data, state, selected_ids, has_boundaries, diet):
        clarify = data.get("clarify")
        if isinstance(clarify, str) and clarify.strip() and not data.get("steps"):
            state.diagnostics.append(self._diagnostic(data, "clarify", state.attempt))
            return self._build_result(state, clarify=clarify.strip())
        try:
            plan = GeoQueryPlan.model_validate(data)
            validate_plan(plan, selected_ids, has_user_geometry=has_boundaries)
            state.diagnostics.append(self._diagnostic(data, "accepted", state.attempt))
            return self._build_result(state, plan=plan)
        except (ValidationError, PlanValidationError) as exc:
            state.diagnostics.append(
                self._diagnostic(data, "rejected", state.attempt, exc)
            )
            state.user = self._correction_message(data, exc, state, diet)
            return None

    def _handle_tool(self, data, selected_ids, state, diet) -> None:
        state.diagnostics.append(
            self._diagnostic(data, "tool_requested", state.attempt + 1)
        )
        if data.get("tool") == self._SKILL_TOOL:
            self._handle_skill(data, state, diet)
            return
        layer_id = str(data.get("layer_id") or "").strip()
        field = str(data.get("field") or "").strip()
        state.tool_calls.append({"layer_id": layer_id, "field": field})
        values = self._sample(layer_id, field, selected_ids, diet)
        state.tool_notes.append(self._sample_note(layer_id, field, values, diet))
        state.user = self._with_tool_notes(state.query, state.tool_notes)

    def _handle_skill(self, data, state, diet) -> None:
        skill_id = str(data.get("skill_id") or "").strip()
        state.tool_calls.append({"skill_id": skill_id})
        try:
            content = self._skill_loader(skill_id, diet) if self._skill_loader else ""
        except Exception:
            content = ""
        note = (
            f"Loaded custom skill {skill_id}:\n{content}"
            if content else f"No custom skill available with id {skill_id}."
        )
        state.tool_notes.append(note)
        state.user = self._with_tool_notes(state.query, state.tool_notes)

    def _sample(self, layer_id, field, selected_ids, diet):
        if layer_id not in selected_ids or not field:
            return []
        try:
            return self._catalog.sample_field(
                layer_id, field, limit=8 if diet else 20
            )
        except Exception:
            return []

    @staticmethod
    def _sample_note(layer_id, field, values, diet) -> str:
        if not values:
            return f"No values available for layer {layer_id} field {field}."
        limit, chars = (8, 24) if diet else (20, 40)
        rendered = json.dumps(
            [str(value)[:chars] for value in values[:limit]], ensure_ascii=False
        )
        return f"Field values for layer {layer_id} field {field}: {rendered}"

    @staticmethod
    def _with_tool_notes(query, notes) -> str:
        return (query.strip() + "\n\n" + "\n".join(notes)
                + "\nNow return the plan (or clarify) as JSON only.")

    @staticmethod
    def _correction_message(data, error, state, diet) -> str:
        error_chars, plan_chars = (300, 800) if diet else (500, 1500)
        notes = ("\n" + "\n".join(state.tool_notes)) if state.tool_notes else ""
        return (
            state.query.strip() + notes + "\n\nYour previous plan was REJECTED: "
            + str(error)[:error_chars] + "\nPrevious plan: "
            + json.dumps(data, ensure_ascii=False)[:plan_chars]
            + "\nReturn a corrected plan as JSON only."
        )

    @staticmethod
    def _diagnostic(data, status, attempt, error=None) -> dict:
        diagnostic = {"attempt": attempt, "status": status, "model_output": data}
        if error is not None:
            diagnostic.update({"error_type": type(error).__name__, "error": str(error)})
        return diagnostic

    @classmethod
    def _is_tool_request(cls, data, state) -> bool:
        if data.get("tool") == cls._SAMPLE_TOOL:
            used = sum("layer_id" in call for call in state.tool_calls)
            return used < cls._MAX_SAMPLE_ROUNDS
        if data.get("tool") != cls._SKILL_TOOL:
            return False
        skill_id = str(data.get("skill_id") or "").strip()
        loaded = {call.get("skill_id") for call in state.tool_calls}
        used = sum("skill_id" in call for call in state.tool_calls)
        return bool(skill_id) and skill_id not in loaded and used < cls._MAX_SKILL_ROUNDS

    @staticmethod
    def _build_result(state, plan=None, clarify=None) -> PlanBuildResult:
        return PlanBuildResult(
            plan=plan, clarify=clarify, attempts=state.attempt,
            token_usage=state.usage.total, tool_calls=state.tool_calls,
            diagnostics=state.diagnostics,
        )
