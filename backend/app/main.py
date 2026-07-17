"""Application composition root."""

from fastapi import FastAPI

from app.application_state_wiring import ApplicationStateWiring
from app.common.config import get_settings
from app.error_handler_registry import ErrorHandlerRegistry
from app.health_router import HealthRouter
from app.service import (
    agent_router, catalog_router, feedback_router, models_router,
    plan_router, query_router, settings_router,
)

_ROUTERS = (
    query_router, plan_router, settings_router, agent_router,
    feedback_router, catalog_router, models_router,
)


class ApplicationFactory:
    @staticmethod
    def create() -> FastAPI:
        application = FastAPI(title="AiLocator", version="0.1.0")
        ApplicationStateWiring.wire(application, get_settings())
        ErrorHandlerRegistry.register(application)
        for module in _ROUTERS:
            application.include_router(module.router)
        application.add_api_route("/health", HealthRouter.status, methods=["GET"])
        return application


create_app = ApplicationFactory.create
_wire_state = ApplicationStateWiring.wire
_register_error_handlers = ErrorHandlerRegistry.register
app = create_app()
