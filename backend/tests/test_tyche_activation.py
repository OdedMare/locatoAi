from unittest.mock import Mock

import geopandas as gpd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.bl.catalog.tyche_activation import activate_tyche_layer
from app.common.errors.provider_error import ProviderError
from app.main import _register_error_handlers
from app.service import catalog_router
from tests.conftest import FakeLayersRepository


class RecordingLog:
    def __init__(self):
        self.events = []

    def info(self, event, **context):
        self.events.append((event, context))

    def error(self, event, **context):
        self.events.append((event, context))


def test_activation_probes_then_idempotently_upserts_catalog_layer():
    repository = FakeLayersRepository([])
    provider = Mock()
    provider.fetch_features.return_value = gpd.GeoDataFrame()

    first, created, sample_count = activate_tyche_layer(repository, provider)
    second, created_again, _ = activate_tyche_layer(repository, provider)

    assert created is True
    assert created_again is False
    assert first.id == second.id
    assert first.provider == "tyche"
    assert first.source_url == "tyche://ourforces"
    assert first.name == "כוחותינו"
    assert sample_count == 0
    assert len(repository.list_layers()) == 1
    assert provider.fetch_features.call_args.kwargs == {"limit": 1}


def test_failed_tyche_probe_does_not_modify_catalog():
    repository = FakeLayersRepository([])
    provider = Mock()
    provider.fetch_features.side_effect = ProviderError("Tyche unavailable")

    with pytest.raises(ProviderError, match="unavailable"):
        activate_tyche_layer(repository, provider)

    assert repository.list_layers() == []


def test_activation_endpoint_returns_layer_and_logs_probe_result():
    app = FastAPI()
    _register_error_handlers(app)
    app.include_router(catalog_router.router)
    app.state.repository = FakeLayersRepository([])
    app.state.tyche_provider = Mock()
    app.state.tyche_provider.fetch_features.return_value = gpd.GeoDataFrame()
    app.state.request_log = RecordingLog()

    response = TestClient(app).post("/api/layers/activate-tyche")

    assert response.status_code == 200
    assert response.json()["name"] == "כוחותינו"
    event, context = app.state.request_log.events[0]
    assert event == "tyche_layer_activated"
    assert context["created"] is True
    assert context["sample_count"] == 0
