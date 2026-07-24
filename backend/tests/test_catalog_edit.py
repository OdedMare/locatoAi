from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.bl.catalog.catalog_service import CatalogService
from app.bl.catalog.models.layer_meta import LayerMeta
from app.main import _register_error_handlers
from app.service.catalog import router as catalog_router
from tests.conftest import FakeLayersRepository


def make_app(repository: FakeLayersRepository) -> FastAPI:
    app = FastAPI()
    _register_error_handlers(app)
    app.include_router(catalog_router.router)
    app.state.catalog = CatalogService(repository, Mock())
    app.state.request_log = Mock()
    return app


def test_edit_layer_updates_metadata_but_preserves_source_identity():
    original = LayerMeta(
        id="layer-1", name="Old", description="Old description",
        tags=["old"], provider="tyche", source_url="tyche://ourforces",
    )
    repository = FakeLayersRepository([original])
    response = TestClient(make_app(repository)).put(
        "/api/layers/layer-1",
        json={
            "name": "כוחותינו", "description": "תיאור חדש",
            "tags": ["כוחות", "כוחות", " movement "],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": "layer-1", "name": "כוחותינו",
        "description": "תיאור חדש", "tags": ["כוחות", "movement"],
        "entity_field": None, "display_field": None, "profiles": [],
    }
    persisted = repository.get_layer("layer-1")
    assert persisted.provider == "tyche"
    assert persisted.source_url == "tyche://ourforces"


def test_edit_unknown_layer_returns_404():
    response = TestClient(
        make_app(FakeLayersRepository([])), raise_server_exceptions=False,
    ).put(
        "/api/layers/missing",
        json={"name": "name", "description": "", "tags": []},
    )
    assert response.status_code == 404


def test_delete_layer_removes_it_from_the_catalog():
    layer = LayerMeta(
        id="layer-1", name="Delete me", provider="mqs",
        source_url="mqs://layer/delete-me",
    )
    repository = FakeLayersRepository([layer])

    response = TestClient(make_app(repository)).delete("/api/layers/layer-1")

    assert response.status_code == 204
    assert response.content == b""
    assert repository.get_layer("layer-1") is None


def test_delete_unknown_layer_returns_404():
    response = TestClient(
        make_app(FakeLayersRepository([])), raise_server_exceptions=False,
    ).delete("/api/layers/missing")

    assert response.status_code == 404


def test_create_layer_persists_declared_entity_role_as_metadata():
    repository = FakeLayersRepository([])
    response = TestClient(make_app(repository)).post(
        "/api/layers",
        json={
            "name": "Tracks", "provider": "flapi",
            "source_url": "flapi://cube/tracks",
            "entity_field": "trackId", "tags": ["movement"],
        },
    )

    assert response.status_code == 201
    assert response.json()["tags"] == ["movement"]
    assert response.json()["entity_field"] == "trackId"
    assert repository.list_layers()[0].persisted_tags() == [
        "entity_field:trackId", "movement",
    ]


def test_legacy_semantic_tags_are_typed_and_hidden_from_business_tags():
    layer = LayerMeta(
        id="legacy", name="Friends", provider="mqs",
        source_url="mqs://layer/friends",
        tags=[
            "entity_field:friend_id", "display_field:friend_name",
            "profile:friends", "people",
        ],
    )

    assert layer.entity_field == "friend_id"
    assert layer.display_field == "friend_name"
    assert layer.profiles == ["friends"]
    assert layer.tags == ["people"]


def test_layer_fields_endpoint_returns_live_schema(catalog):
    app = FastAPI()
    _register_error_handlers(app)
    app.include_router(catalog_router.router)
    app.state.catalog = catalog

    response = TestClient(app).get("/api/layers/schools/fields")

    assert response.status_code == 200
    assert "city_en" in response.json()["fields"]
