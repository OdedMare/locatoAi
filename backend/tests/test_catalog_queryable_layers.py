from unittest.mock import Mock

from app.bl.agent.select_layers.layer_selector import LayerSelector
from app.bl.catalog.catalog_service import CatalogService
from app.dal.providers.registry import InMemoryProviderRegistry
from tests.conftest import FakeLayersRepository, LAYERS


def test_queryable_layers_exclude_unregistered_legacy_providers():
    catalog = CatalogService(
        FakeLayersRepository(LAYERS), InMemoryProviderRegistry()
    )

    assert len(catalog.list_layers()) == len(LAYERS)
    assert catalog.list_queryable_layers() == []


def test_selector_clarifies_without_calling_llm_when_no_provider_is_active():
    llm = Mock()
    catalog = CatalogService(
        FakeLayersRepository(LAYERS), InMemoryProviderRegistry()
    )

    selection = LayerSelector(llm, catalog).select("כיכרות")

    assert selection.layers == []
    assert "שכבות מידע פעילות" in selection.clarify
    llm.complete_json.assert_not_called()
