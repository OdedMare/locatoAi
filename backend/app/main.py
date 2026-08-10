"""Application composition root."""

from fastapi import FastAPI

from app.application_state_wiring import wire
from app.common.config.settings_provider import get_settings
from app.service.errors.registry import register_error_handlers
from app.service.health.router import status
from app.service.agent.router import router as agent_router
from app.service.agent_config.router import router as agent_config_router
from app.service.area_summary.router import router as area_summary_router
from app.service.catalog.router import router as catalog_router
from app.service.feedback.router import router as feedback_router
from app.service.models.router import router as models_router
from app.service.plan.router import router as plan_router
from app.service.query.router import router as query_router
from app.service.ranking.router import router as ranking_router
from app.service.settings.router import router as settings_router

_ROUTERS = (
    query_router, plan_router, settings_router, agent_router,
    agent_config_router, feedback_router, catalog_router, models_router,
    area_summary_router, ranking_router,
)


def create_app() -> FastAPI:
    application = FastAPI(title="AiLocator", version="0.1.0")
    wire(application, get_settings())
    application.add_event_handler(
        "shutdown", application.state.query_runs.shutdown,
    )
    register_error_handlers(application)
    for router in _ROUTERS:
        application.include_router(router)
    application.add_api_route("/health", status, methods=["GET"])
    return application


_wire_state = wire
_register_error_handlers = register_error_handlers
app = create_app()
