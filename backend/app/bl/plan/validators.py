"""Semantic plan validation beyond what Pydantic can express.

These run after parsing and before execution. When the agent lands
(Day 2), a failure here triggers one retry with the error appended to
the prompt, then a clarify fallback.
"""

from typing import Set

from app.bl.plan.models import (
    BetweenStep,
    ContainsStep,
    CountStep,
    GeoQueryPlan,
    LoadStep,
    NearestNStep,
    NearStep,
    CrossesStep,
    TouchesStep,
    WithinGeometryStep,
)
from app.common.errors import PlanValidationError


def validate_plan(
    plan: GeoQueryPlan,
    known_layer_ids: Set[str],
    has_user_geometry: bool,
) -> None:
    """Raise PlanValidationError with a clear, agent-readable message."""
    seen_ids: Set[str] = set()

    for step in plan.steps:
        if step.id in seen_ids:
            raise PlanValidationError(f"Duplicate step id: '{step.id}'")

        # `input` must reference an EARLIER step — this both guarantees the
        # DAG is acyclic and lets the engine execute in list order.
        input_ref = getattr(step, "input", None)
        if input_ref is not None and input_ref not in seen_ids:
            raise PlanValidationError(
                f"Step '{step.id}': input '{input_ref}' does not reference an earlier step"
            )

        if isinstance(step, LoadStep) and step.layer not in known_layer_ids:
            raise PlanValidationError(
                f"Step '{step.id}': layer '{step.layer}' is not in the catalog"
            )
        if isinstance(step, NearStep) and step.target_layer not in known_layer_ids:
            raise PlanValidationError(
                f"Step '{step.id}': target_layer '{step.target_layer}' is not in the catalog"
            )
        if isinstance(
            step, (NearStep, NearestNStep, CrossesStep, TouchesStep, ContainsStep)
        ):
            if step.target_layer not in known_layer_ids:
                raise PlanValidationError(
                    f"Step '{step.id}': target_layer '{step.target_layer}' "
                    "is not in the catalog"
                )
            target_filter = (
                step.target_field, step.target_operator, step.target_value
            )
            if any(value is not None for value in target_filter) and not all(
                value is not None for value in target_filter
            ):
                raise PlanValidationError(
                    f"Step '{step.id}': target_field, target_operator and "
                    "target_value must be supplied together"
                )
        if isinstance(step, BetweenStep):
            for label, layer_id in (
                ("first_target_layer", step.first_target_layer),
                ("second_target_layer", step.second_target_layer),
            ):
                if layer_id not in known_layer_ids:
                    raise PlanValidationError(
                        f"Step '{step.id}': {label} '{layer_id}' is not in the catalog"
                    )
            for prefix in ("first", "second"):
                target_filter = (
                    getattr(step, f"{prefix}_target_field"),
                    getattr(step, f"{prefix}_target_operator"),
                    getattr(step, f"{prefix}_target_value"),
                )
                if any(value is not None for value in target_filter) and not all(
                    value is not None for value in target_filter
                ):
                    raise PlanValidationError(
                        f"Step '{step.id}': {prefix}_target_field, "
                        f"{prefix}_target_operator and {prefix}_target_value "
                        "must be supplied together"
                    )
        if isinstance(step, NearestNStep) and step.target_layer not in known_layer_ids:
            raise PlanValidationError(
                f"Step '{step.id}': target_layer '{step.target_layer}' is not in the catalog"
            )
        if isinstance(step, WithinGeometryStep) and not has_user_geometry:
            raise PlanValidationError(
                f"Step '{step.id}': plan uses within_geometry but the request has no boundaries"
            )

        seen_ids.add(step.id)

    if not plan.steps:
        raise PlanValidationError("Plan has no steps")
    if plan.output not in seen_ids:
        raise PlanValidationError(f"Plan output '{plan.output}' is not a step id")

    # count is terminal-only: it must BE the output, and nothing may chain
    # off it as `input` (a scalar int has no features to feed onward).
    count_step_ids = {step.id for step in plan.steps if isinstance(step, CountStep)}
    if count_step_ids:
        referenced_as_input = {getattr(step, "input", None) for step in plan.steps}
        bad_refs = count_step_ids & referenced_as_input
        if bad_refs:
            raise PlanValidationError(
                f"Step(s) {sorted(bad_refs)}: a 'count' step cannot be used "
                "as another step's input"
            )
        if plan.output not in count_step_ids:
            raise PlanValidationError(
                "Plan has a 'count' step but it is not the plan's output — "
                "'count' must be the final, output step"
            )

    if plan.steps and plan.output != plan.steps[-1].id:
        raise PlanValidationError(
            f"Plan output '{plan.output}' must be the final step "
            f"('{plan.steps[-1].id}')"
        )
