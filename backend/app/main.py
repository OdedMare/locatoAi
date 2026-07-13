"""Composition root: wires DAL implementations into BL ports and mounts
the service routers. The only module that knows every tier."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.bl.agent.build_plan import PlanBuilder
from app.bl.agent.select_layers import LayerSelector
from app.bl.catalog.catalog_service import CatalogService
from app.bl.executor.engine import PlanExecutor
from app.bl.query_orchestrator import QueryOrchestrator
from app.common.config import Settings, get_settings
from app.common.errors import (
    AgentError,
    ExecutionError,
    LayerNotFoundError,
    PlanValidationError,
    ProviderError,
)
from app.common.logging import configure_logging
from app.common.runtime_settings import RuntimeSettingsStore
from app.dal.layers_repository import PostgresLayersRepository
from app.dal.llm.openai_client import OpenAIJsonClient
from app.dal.providers.arcgis_mock import MockArcgisProvider
from app.dal.providers.mqs import MqsProvider
from app.dal.providers.registry import InMemoryProviderRegistry
from app.service import (
    agent_router,
    catalog_router,
    feedback_router,
    models_router,
    plan_router,
    query_router,
    settings_router,
)

_ERROR_STATUS = {
    LayerNotFoundError: 404,
    PlanValidationError: 422,
    ProviderError: 502,
    ExecutionError: 400,
    AgentError: 503,
}

_ROUTERS = (
    query_router,
    plan_router,
    settings_router,
    agent_router,
    feedback_router,
    catalog_router,
    models_router,
)


def _wire_state(app: FastAPI, settings: Settings) -> None:
    """Build the object graph (DAL implementations → BL ports) on app.state."""
    settings_store = RuntimeSettingsStore(settings)

    repository = PostgresLayersRepository(settings_store)
    providers = InMemoryProviderRegistry()
    providers.register("arcgis", MockArcgisProvider(settings.data_dir))
    mqs_provider = MqsProvider(settings_store)
    providers.register("mqs", mqs_provider)

    catalog = CatalogService(
        repository, providers, schema_ttl_seconds=settings.schema_cache_ttl_seconds
    )
    executor = PlanExecutor(catalog, providers)
    llm = OpenAIJsonClient(settings_store)
    layer_selector = LayerSelector(llm, catalog)
    plan_builder = PlanBuilder(llm, catalog)

    app.state.settings_store = settings_store
    app.state.repository = repository
    app.state.mqs_provider = mqs_provider  # catalog_router's sync endpoint
    app.state.catalog = catalog
    app.state.layer_selector = layer_selector
    app.state.llm_client = llm
    app.state.orchestrator = QueryOrchestrator(
        catalog, executor, layer_selector=layer_selector, plan_builder=plan_builder
    )
    app.state.request_log = configure_logging(settings.request_log_path)


def _register_error_handlers(app: FastAPI) -> None:
    """Map domain exceptions to HTTP statuses with a uniform error body."""

    def make_handler(status_code: int):
        async def handler(request: Request, exc: Exception) -> JSONResponse:
            return JSONResponse(
                status_code=status_code,
                content={"status": "error", "detail": str(exc)},
            )

        return handler

    for error_type, status_code in _ERROR_STATUS.items():
        app.add_exception_handler(error_type, make_handler(status_code))


def create_app() -> FastAPI:
    app = FastAPI(title="AiLocator", version="0.1.0")

    _wire_state(app, get_settings())
    _register_error_handlers(app)
    for module in _ROUTERS:
        app.include_router(module.router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
