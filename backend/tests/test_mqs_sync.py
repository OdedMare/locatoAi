from typing import List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.bl.catalog.mqs_sync.browse_mqs_layers import browse_mqs_layers
from app.bl.catalog.mqs_sync.sync_mqs_layers import sync_mqs_layers
from app.common.errors.provider_error import ProviderError
from app.main import _register_error_handlers
from app.service.catalog import router as catalog_router
from app.service.catalog.router import _normalized_source
from tests.conftest import FakeLayersRepository


class FakeMqsProvider:
    def __init__(self, layers: List[dict]):
        self._layers = layers

    def list_remote_layers(self) -> List[dict]:
        if isinstance(self._layers, Exception):
            raise self._layers
        return self._layers


def test_first_sync_adds_all():
    repository = FakeLayersRepository([])
    provider = FakeMqsProvider([
        {"id": 1, "name": "כבישים", "description": "רשת הכבישים"},
        {"layerId": "2", "title": "פארקים", "tags": ["nature", "park", "nature"]},
    ])
    result = sync_mqs_layers(repository, provider)
    assert (result.added, result.updated, result.skipped) == (2, 0, 0)
    layers = repository.list_layers()
    assert all(layer.provider == "mqs" for layer in layers)
    by_url = {layer.source_url: layer for layer in layers}
    assert by_url["mqs://layer/1"].name == "כבישים"
    assert by_url["mqs://layer/2"].name == "פארקים"
    assert by_url["mqs://layer/2"].tags == ["nature", "park"]  # deduped


def test_resync_updates_in_place_and_preserves_tags():
    repository = FakeLayersRepository([])
    sync_mqs_layers(repository, FakeMqsProvider([{"id": 1, "name": "old"}]))
    layer = repository.list_layers()[0]
    # simulate LLM tag enrichment after the first sync
    repository._layers[layer.id] = layer.model_copy(update={"tags": ["enriched"]})

    result = sync_mqs_layers(
        repository, FakeMqsProvider([{"id": 1, "name": "new name", "tags": ["raw"]}])
    )
    assert (result.added, result.updated) == (0, 1)
    layers = repository.list_layers()
    assert len(layers) == 1
    assert layers[0].name == "new name"
    assert layers[0].tags == ["enriched"]  # update must not clobber tags


def test_entry_without_id_is_skipped():
    repository = FakeLayersRepository([])
    result = sync_mqs_layers(
        repository, FakeMqsProvider([{"name": "no id"}, {"id": 7}])
    )
    assert (result.added, result.skipped) == (1, 1)
    layer = repository.list_layers()[0]
    assert layer.name == "MQS layer 7"  # name fallback


def test_browse_normalizes_without_inserting():
    repository = FakeLayersRepository([])
    layers, skipped = browse_mqs_layers(FakeMqsProvider([
        {"layerId": 3, "title": "Trees", "tags": ["green", "green"]},
        {"name": "missing id"},
    ]))
    assert skipped == 1
    assert repository.list_layers() == []
    assert layers[0].source_url == "mqs://layer/3"
    assert layers[0].tags == ["green"]


def test_browse_uses_mqs_display_name():
    layers, skipped = browse_mqs_layers(FakeMqsProvider([
        {"layer_id": 7, "display_name": "כבישים ודרכים"},
    ]))
    assert skipped == 0
    assert layers[0].id == "7"
    assert layers[0].name == "כבישים ודרכים"


def test_sync_saves_full_mqs_object_id_and_name():
    repository = FakeLayersRepository([])
    result = sync_mqs_layers(repository, FakeMqsProvider([{
        "display_name": "כבישים ודרכים",
        "unclassified_description": "שכבת פרויקט אזרחי",
        "name": "T_ROADS",
        "exclusive_id": {
            "data_store_name": "MoriaProject",
            "layer_id": "110",
        },
    }]))
    assert (result.added, result.skipped) == (1, 0)
    saved = repository.list_layers()[0]
    assert saved.name == "כבישים ודרכים"
    assert saved.description == "שכבת פרויקט אזרחי"
    assert saved.provider == "mqs"
    assert saved.source_url == "mqs://layer/110"


def make_app(repository, provider) -> FastAPI:
    app = FastAPI()
    _register_error_handlers(app)
    app.include_router(catalog_router.router)
    app.state.repository = repository
    app.state.mqs_provider = provider
    return app


def test_sync_endpoint_returns_counts():
    app = make_app(FakeLayersRepository([]), FakeMqsProvider([{"id": 1}, {"id": 2}]))
    client = TestClient(app)
    response = client.post("/api/layers/sync-mqs")
    assert response.status_code == 200
    assert response.json() == {"added": 2, "updated": 0, "skipped": 0, "total": 2}


def test_sync_endpoint_provider_error_is_502():
    app = make_app(
        FakeLayersRepository([]),
        FakeMqsProvider(ProviderError("MQS base URL is not configured")),
    )
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/api/layers/sync-mqs")
    assert response.status_code == 502
    assert "not configured" in response.json()["detail"]


def test_browse_endpoint_does_not_insert():
    repository = FakeLayersRepository([])
    app = make_app(repository, FakeMqsProvider([{"id": 4, "name": "Buildings"}]))
    response = TestClient(app).get("/api/layers/mqs")
    assert response.status_code == 200
    assert response.json()["layers"][0] == {
        "id": "4", "name": "Buildings", "description": "", "tags": [],
        "provider": "mqs", "source_url": "mqs://layer/4",
    }
    assert repository.list_layers() == []


def test_browse_endpoint_unknown_provider_payload_is_502():
    class UnknownPayloadProvider:
        def list_remote_layers(self):
            raise ProviderError("MQS returned an unrecognized layer-list response")

    app = make_app(FakeLayersRepository([]), UnknownPayloadProvider())
    response = TestClient(app, raise_server_exceptions=False).get("/api/layers/mqs")
    assert response.status_code == 502
    assert "unrecognized" in response.json()["detail"]


def test_cubes_database_name_normalizes_to_catalog_source_url():
    assert _normalized_source("cubes", "transport") == "cubes://db/transport"
    assert _normalized_source("cubes", "cubes://db/transport") == "cubes://db/transport"
    assert _normalized_source("tyche", "ourforces") == "tyche://ourforces"
    assert _normalized_source("tyche", "tyche://ourforces") == "tyche://ourforces"
    assert _normalized_source(
        "tyche", "/coordinate/v1/alerts",
        tyche_geometry_field="geo",
        tyche_geo_query_field="area",
        tyche_time_field="observedAt",
    ) == (
        "tyche://coordinate/v1/alerts?"
        "geometry_field=geo&geo_query_field=area&time_field=observedAt"
    )
    assert _normalized_source(
        "cubes", "transport", "match_not"
    ) == "cubes://db/transport?query_mode=match_not"
    assert _normalized_source(
        "cubes", "rastaMorialand", cubes_dynamic_parameters={"fl:dynamic": "612"}
    ) == "cubes://db/rastaMorialand?param_fl%3Adynamic=612"
    assert _normalized_source(
        "cubes",
        "rastaMoriaLand",
        cubes_parameters={"fl:dynamic": "9000", "environment": "prod"},
    ) == (
        "cubes://db/rastaMoriaLand?"
        "param_fl%3Adynamic=9000&param_environment=prod"
    )
    assert _normalized_source(
        "mqs", "mqs://layer/42", "match_not"
    ) == "mqs://layer/42"
