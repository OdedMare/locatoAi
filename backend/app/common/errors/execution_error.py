from app.common.errors.ailocator_error import AiLocatorError


class ExecutionError(AiLocatorError):
    """A plan step failed at execution time (bad field, empty input...)."""
