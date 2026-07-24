"""Build and assign the application's dependency graph."""

from app.bl.agent.build_plan.plan_builder import PlanBuilder
from app.bl.agent.generate_layer_metadata.layer_metadata_generator import LayerMetadataGenerator
from app.bl.agent.select_layers.layer_selector import LayerSelector
from app.bl.catalog.catalog_service import CatalogService
from app.bl.executor.engine.plan_executor import PlanExecutor
from app.bl.query_orchestrator.query_orchestrator import QueryOrchestrator
from app.common.logging.configurator import configure_logging
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.feedback.feedback_repository import PostgresFeedbackRepository
from app.dal.agent_content.repository import AgentContentRepository
from app.dal.catalog.layers_repository import PostgresLayersRepository
from app.dal.llm.openai_client import OpenAIJsonClient
from app.dal.providers.flapi.provider import FlapiProvider
from app.dal.providers.mqs.provider import MqsProvider
from app.dal.providers.registry import InMemoryProviderRegistry
from app.dal.providers.tyche.provider import TycheProvider
from app.bl.agent.runtime_diet_mode import RuntimeDietMode


class ApplicationStateWiring:
    @classmethod
    def wire(cls, app, settings) -> None:
        store = RuntimeSettingsStore(settings)
        agent_content = AgentContentRepository(store)
        repository = PostgresLayersRepository(store)
        providers = cls._providers(store, settings)
        services = cls._services(
            store, repository, providers, settings, agent_content
        )
        cls._assign(
            app, store, repository, providers, services, settings, agent_content
        )

    @staticmethod
    def _providers(store, settings):
        registry = InMemoryProviderRegistry()
        mqs = MqsProvider(store, detail_concurrency=settings.mqs_detail_concurrency)
        flapi = FlapiProvider(store)
        tyche = TycheProvider(store)
        registry.register("mqs", mqs)
        registry.register("cubes", flapi)
        registry.register("flapi", flapi)
        registry.register("tyche", tyche)
        return registry, mqs, flapi, tyche

    @staticmethod
    def _services(
        store, repository, provider_bundle, settings, agent_content
    ):
        providers = provider_bundle[0]
        catalog = CatalogService(
            repository, providers,
            schema_ttl_seconds=settings.schema_cache_ttl_seconds,
        )
        executor = PlanExecutor(catalog, providers)
        llm = OpenAIJsonClient(store)
        diet_mode = RuntimeDietMode(store)
        selector = LayerSelector(
            llm, catalog, diet_mode=diet_mode,
            content_repository=agent_content,
        )
        builder = PlanBuilder(
            llm, catalog, diet_mode=diet_mode,
            content_repository=agent_content,
        )
        metadata = LayerMetadataGenerator(
            llm, providers, content_repository=agent_content
        )
        orchestrator = QueryOrchestrator(
            catalog, executor, layer_selector=selector, plan_builder=builder
        )
        return catalog, llm, selector, metadata, orchestrator

    @staticmethod
    def _assign(
        app, store, repository, provider_bundle, services, settings,
        agent_content,
    ) -> None:
        providers, mqs, flapi, tyche = provider_bundle
        catalog, llm, selector, metadata, orchestrator = services
        app.state.settings_store = store
        app.state.agent_content = agent_content
        app.state.repository = repository
        app.state.feedback_repository = PostgresFeedbackRepository(store)
        app.state.mqs_provider = mqs
        app.state.flapi_provider = flapi
        app.state.tyche_provider = tyche
        app.state.catalog = catalog
        app.state.layer_selector = selector
        app.state.llm_client = llm
        app.state.layer_metadata_generator = metadata
        app.state.orchestrator = orchestrator
        app.state.request_log = configure_logging(settings.request_log_path)
