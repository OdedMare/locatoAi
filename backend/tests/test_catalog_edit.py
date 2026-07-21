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
