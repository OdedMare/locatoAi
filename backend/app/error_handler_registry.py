"""Register domain-to-HTTP error mappings."""

from app.common.errors.agent_error import AgentError
from app.common.errors.execution_error import ExecutionError
from app.common.errors.layer_not_found_error import LayerNotFoundError
from app.common.errors.plan_validation_error import PlanValidationError
from app.common.errors.provider_error import ProviderError
from app.error_handler import ErrorHandler


class ErrorHandlerRegistry:
    _STATUSES = {
        LayerNotFoundError: 404,
        PlanValidationError: 422,
        ProviderError: 502,
        ExecutionError: 400,
        AgentError: 503,
    }

    @classmethod
    def register(cls, app) -> None:
        for error_type, status_code in cls._STATUSES.items():
            app.add_exception_handler(error_type, ErrorHandler(status_code))
        app.add_exception_handler(Exception, ErrorHandler(500))
