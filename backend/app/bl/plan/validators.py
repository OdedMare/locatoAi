"""Semantic validation for parsed geographic query plans."""

from typing import Set

from app.bl.plan.models.between_step import BetweenStep
from app.bl.plan.models.contains_step import ContainsStep
from app.bl.plan.models.count_step import CountStep
from app.bl.plan.models.crosses_step import CrossesStep
from app.bl.plan.models.geo_query_plan import GeoQueryPlan
from app.bl.plan.models.load_step import LoadStep
from app.bl.plan.models.near_all_step import NearAllStep
from app.bl.plan.models.near_step import NearStep
from app.bl.plan.models.nearest_n_step import NearestNStep
from app.bl.plan.models.touches_step import TouchesStep
from app.bl.plan.models.within_geometry_step import WithinGeometryStep
from app.common.errors.plan_validation_error import PlanValidationError


class PlanValidator:
    _FILTERED_TARGET_STEPS = (
        NearStep, NearestNStep, CrossesStep, TouchesStep, ContainsStep,
    )

    def validate(
        self, plan: GeoQueryPlan, known_layer_ids: Set[str],
        has_user_geometry: bool,
    ) -> None:
        seen_ids: Set[str] = set()
        for step in plan.steps:
            self._validate_step(step, seen_ids, known_layer_ids, has_user_geometry)
            seen_ids.add(step.id)
        self._validate_count_steps(plan)
        self._validate_shape(plan, seen_ids, has_user_geometry)

    def _validate_step(
        self, step, seen_ids: Set[str], known_layers: Set[str],
        has_user_geometry: bool,
    ) -> None:
        self._validate_identity(step, seen_ids)
        if isinstance(step, LoadStep):
            self._known_layer(step, "layer", step.layer, known_layers)
        if isinstance(step, self._FILTERED_TARGET_STEPS):
            self._validate_target_step(step, known_layers)
        if isinstance(step, BetweenStep):
            self._validate_between(step, known_layers)
        if isinstance(step, NearAllStep):
            self._validate_near_all(step, known_layers)
        if isinstance(step, WithinGeometryStep) and not has_user_geometry:
            raise PlanValidationError(
                f"Step '{step.id}': plan uses within_geometry but the request has no boundaries"
            )

    @staticmethod
    def _validate_identity(step, seen_ids: Set[str]) -> None:
        if step.id in seen_ids:
            raise PlanValidationError(f"Duplicate step id: '{step.id}'")
        input_ref = getattr(step, "input", None)
        if input_ref is not None and input_ref not in seen_ids:
            raise PlanValidationError(
                f"Step '{step.id}': input '{input_ref}' does not reference an earlier step"
            )

    def _validate_target_step(self, step, known_layers: Set[str]) -> None:
        self._known_layer(step, "target_layer", step.target_layer, known_layers)
        self._complete_filter(
            step.id, "target",
            (step.target_field, step.target_operator, step.target_value),
        )

    def _validate_between(self, step: BetweenStep, known_layers: Set[str]) -> None:
        for prefix in ("first", "second"):
            label = f"{prefix}_target_layer"
            self._known_layer(step, label, getattr(step, label), known_layers)
            self._complete_filter(
                step.id, f"{prefix}_target",
                tuple(getattr(step, f"{prefix}_target_{name}")
                      for name in ("field", "operator", "value")),
            )

    def _validate_near_all(self, step: NearAllStep, known_layers: Set[str]) -> None:
        for target in step.targets:
            self._known_layer(step, "target layer", target.layer, known_layers)
            self._complete_filter(
                step.id, "each near_all target",
                (target.field, target.operator, target.value),
            )

    @staticmethod
    def _known_layer(step, label: str, layer_id: str, known_layers: Set[str]) -> None:
        if layer_id not in known_layers:
            raise PlanValidationError(
                f"Step '{step.id}': {label} '{layer_id}' is not in the catalog"
            )

    @staticmethod
    def _complete_filter(step_id: str, label: str, values: tuple) -> None:
        if any(value is not None for value in values) and not all(
            value is not None for value in values
        ):
            raise PlanValidationError(
                f"Step '{step_id}': {label}_field, {label}_operator and "
                f"{label}_value must be supplied together"
            )

    def _validate_shape(
        self, plan: GeoQueryPlan, seen_ids: Set[str], has_geometry: bool,
    ) -> None:
        if not plan.steps:
            raise PlanValidationError("Plan has no steps")
        if has_geometry and not any(
            isinstance(step, WithinGeometryStep) for step in plan.steps
        ):
            raise PlanValidationError(
                "Plan must apply within_geometry because request boundaries are required"
            )
        if plan.output not in seen_ids:
            raise PlanValidationError(f"Plan output '{plan.output}' is not a step id")
        if plan.output != plan.steps[-1].id:
            raise PlanValidationError(
                f"Plan output '{plan.output}' must be the final step ('{plan.steps[-1].id}')"
            )

    @staticmethod
    def _validate_count_steps(plan: GeoQueryPlan) -> None:
        count_ids = {step.id for step in plan.steps if isinstance(step, CountStep)}
        if not count_ids:
            return
        referenced = {getattr(step, "input", None) for step in plan.steps}
        bad_refs = count_ids & referenced
        if bad_refs:
            raise PlanValidationError(
                f"Step(s) {sorted(bad_refs)}: a 'count' step cannot be used "
                "as another step's input"
            )
        if plan.output not in count_ids:
            raise PlanValidationError(
                "Plan has a 'count' step but it is not the plan's output — "
                "'count' must be the final, output step"
            )


validate_plan = PlanValidator().validate
