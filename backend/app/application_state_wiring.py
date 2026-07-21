"""Build and assign the application's dependency graph."""

from app.bl.agent.build_plan.plan_builder import PlanBuilder
from app.bl.agent.generate_layer_metadata.layer_metadata_generator import LayerMetadataGenerator
from app.bl.agent.select_layers.layer_selector import LayerSelector
from app.bl.catalog.catalog_service import CatalogService
from app.bl.executor.engine.plan_executor import PlanExecutor
from app.bl.query_orchestrator.query_orchestrator import QueryOrchestrator
from app.common.logging.configurator import configure_logging
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.feedback_repository import PostgresFeedbackRepository
from app.dal.layers_repository import PostgresLayersRepository
from app.dal.llm.openai_client import OpenAIJsonClient
from app.dal.providers.cubes import CubesProvider
from app.dal.providers.mqs import MqsProvider
from app.dal.providers.registry import InMemoryProviderRegistry
from app.dal.providers.tyche import TycheProvider
from app.runtime_diet_mode import RuntimeDietMode


class ApplicationStateWiring:
    @classmethod
    def wire(cls, app, settings) -> None:
        store = RuntimeSettingsStore(settings)
        repository = PostgresLayersRepository(store)
        providers = cls._providers(store, settings)
        services = cls._services(store, repository, providers, settings)
        cls._assign(app, store, repository, providers, services, settings)

    @staticmethod
    def _providers(store, settings):
        registry = InMemoryProviderRegistry()
        mqs = MqsProvider(store, detail_concurrency=settings.mqs_detail_concurrency)
        cubes = CubesProvider(store)
        tyche = TycheProvider(store)
        registry.register("mqs", mqs)
        registry.register("cubes", cubes)
        registry.register("tyche", tyche)
        return registry, mqs, cubes, tyche

    @staticmethod
    def _services(store, repository, provider_bundle, settings):
        providers = provider_bundle[0]
        catalog = CatalogService(
            repository, providers,
            schema_ttl_seconds=settings.schema_cache_ttl_seconds,
        )
        executor = PlanExecutor(catalog, providers)
        llm = OpenAIJsonClient(store)
        diet_mode = RuntimeDietMode(store)
        selector = LayerSelector(llm, catalog, diet_mode=diet_mode)
        builder = PlanBuilder(llm, catalog, diet_mode=diet_mode)
        metadata = LayerMetadataGenerator(llm, providers)
        orchestrator = QueryOrchestrator(
            catalog, executor, layer_selector=selector, plan_builder=builder
        )
        return catalog, llm, selector, metadata, orchestrator

    @staticmethod
    def _assign(app, store, repository, provider_bundle, services, settings) -> None:
        providers, mqs, cubes, tyche = provider_bundle
        catalog, llm, selector, metadata, orchestrator = services
        app.state.settings_store = store
        app.state.repository = repository
        app.state.feedback_repository = PostgresFeedbackRepository(store)
        app.state.mqs_provider = mqs
        app.state.cubes_provider = cubes
        app.state.tyche_provider = tyche
        app.state.catalog = catalog
        app.state.layer_selector = selector
        app.state.llm_client = llm
        app.state.layer_metadata_generator = metadata
        app.state.orchestrator = orchestrator
        app.state.request_log = configure_logging(settings.request_log_path)
