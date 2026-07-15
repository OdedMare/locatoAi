from app.common.errors.ailocator_error import AiLocatorError


class PlanValidationError(AiLocatorError):
    """The plan is structurally invalid (bad refs, cycles, unknown layers...)."""
