import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.common.config.settings import Settings
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.providers.cubes import CubesProvider
from app.main import _register_error_handlers
from app.service import catalog_router


def make_app(handler, tmp_path) -> FastAPI:
    app = FastAPI()
    _register_error_handlers(app)
    app.include_router(catalog_router.router)
    store = RuntimeSettingsStore(Settings(
        _env_file=None,
        runtime_settings_file=str(tmp_path / "runtime-settings.json"),
        cubes_base_url="https://cubes.test",
        cubes_token="jwt",
    ))
    app.state.cubes_provider = CubesProvider(store, httpx.MockTransport(handler))
    return app


def test_autocomplete_endpoint_returns_live_options(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/cube/v1/transport/autocomplete/sourceSystems"
        return httpx.Response(200, json=[
            {"Value": "system-a", "Name": "System A"},
            {"Value": "system-b", "Name": "System B"},
        ])

    response = TestClient(make_app(handler, tmp_path)).post(
        "/api/layers/autocomplete-parameter",
        json={"source_url": "cubes://db/transport", "parameter_name": "sourceSystems"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "options": [
            {"value": "system-a", "name": "System A"},
            {"value": "system-b", "name": "System B"},
        ]
    }


def test_autocomplete_endpoint_preserves_fl_dynamic_name(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/cube/v1/rastaMorialand/autocomplete/fl:dynamic"
        return httpx.Response(200, json=[
            {"Value": "612", "Name": "Layer 612"},
            {"Value": "845", "Name": "Layer 845"},
        ])

    response = TestClient(make_app(handler, tmp_path)).post(
        "/api/layers/autocomplete-parameter",
        json={
            "source_url": "cubes://db/rastaMorialand",
            "parameter_name": "fl:dynamic",
        },
    )

    assert response.status_code == 200
    assert response.json()["options"] == [
        {"value": "612", "name": "Layer 612"},
        {"value": "845", "name": "Layer 845"},
    ]


def test_autocomplete_endpoint_maps_provider_failure_to_502(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "cube unavailable"})

    response = TestClient(
        make_app(handler, tmp_path), raise_server_exceptions=False,
    ).post(
        "/api/layers/autocomplete-parameter",
        json={"source_url": "cubes://db/transport", "parameter_name": "sourceSystems"},
    )

    assert response.status_code == 502
