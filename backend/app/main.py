"""Application composition root."""

from fastapi import FastAPI

from app.application_state_wiring import ApplicationStateWiring
from app.common.config.settings_provider import get_settings
from app.service.errors.registry import ErrorHandlerRegistry
from app.service.health.router import HealthRouter
from app.service.agent.router import router as agent_router
from app.service.catalog.router import router as catalog_router
from app.service.feedback.router import router as feedback_router
from app.service.models.router import router as models_router
from app.service.plan.router import router as plan_router
from app.service.query.router import router as query_router
from app.service.settings.router import router as settings_router

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
        for router in _ROUTERS:
            application.include_router(router)
        application.add_api_route("/health", HealthRouter.status, methods=["GET"])
        return application


create_app = ApplicationFactory.create
_wire_state = ApplicationStateWiring.wire
_register_error_handlers = ErrorHandlerRegistry.register
app = create_app()
