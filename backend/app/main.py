"""Composition root: wires DAL implementations into BL ports and mounts
the service routers. The only module that knows every tier."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.bl.agent.select_layers import LayerSelector
from app.bl.catalog.catalog_service import CatalogService
from app.bl.executor.engine import PlanExecutor
from app.bl.query_orchestrator import QueryOrchestrator
from app.common.config import get_settings
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
from app.dal.providers.registry import ProviderRegistryImpl
from app.service import agent_router, plan_router, query_router, settings_router

_ERROR_STATUS = {
    LayerNotFoundError: 404,
    PlanValidationError: 422,
    ProviderError: 502,
    ExecutionError: 400,
    AgentError: 503,
}


def create_app() -> FastAPI:
    settings = get_settings()
    settings_store = RuntimeSettingsStore(settings)

    repository = PostgresLayersRepository(settings_store)
    providers = ProviderRegistryImpl()
    providers.register("arcgis", MockArcgisProvider(settings.data_dir))

    catalog = CatalogService(
        repository, providers, schema_ttl_seconds=settings.schema_cache_ttl_seconds
    )
    executor = PlanExecutor(catalog, providers)
    llm = OpenAIJsonClient(settings_store)
    layer_selector = LayerSelector(llm, catalog)

    app = FastAPI(title="AiLocator", version="0.1.0")
    app.state.orchestrator = QueryOrchestrator(
        catalog, executor, layer_selector=layer_selector
    )
    app.state.catalog = catalog
    app.state.repository = repository
    app.state.settings_store = settings_store
    app.state.layer_selector = layer_selector
    app.state.request_log = configure_logging(settings.request_log_path)

    app.include_router(query_router.router)
    app.include_router(plan_router.router)
    app.include_router(settings_router.router)
    app.include_router(agent_router.router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    for error_type, status_code in _ERROR_STATUS.items():
        @app.exception_handler(error_type)
        async def handle(request: Request, exc: Exception, _code=status_code):
            return JSONResponse(
                status_code=_code,
                content={"status": "error", "detail": str(exc)},
            )

    return app


app = create_app()
