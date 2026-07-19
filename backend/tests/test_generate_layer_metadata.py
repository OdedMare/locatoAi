import json
from types import SimpleNamespace

import geopandas as gpd
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from shapely.geometry import Point

from app.bl.agent.generate_layer_metadata.layer_metadata_generator import (
    LayerMetadataGenerator,
)
from app.bl.agent.generate_layer_metadata.generated_layer_metadata import (
    GeneratedLayerMetadata,
)
from app.bl.ports.layer_field import LayerField
from app.bl.ports.layer_parameter import LayerParameter
from app.bl.ports.layer_schema import LayerSchema
from app.common.config import Settings
from app.common.errors.provider_error import ProviderError
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.providers.mqs import MqsProvider
from app.dal.providers.registry import InMemoryProviderRegistry
from app.main import _register_error_handlers
from app.service import catalog_router
from app.service.catalog_dto.generate_layer_metadata_request import (
    GenerateLayerMetadataRequest,
)
from app.service.catalog_router import CatalogRouter
from tests.test_cubes_provider import make_provider as make_cubes_provider


class SampleProvider:
    def __init__(self):
        self.fetch_features_limit = "not called"

    def fetch_features(self, layer, now=None, geometry=None, limit=None):
        self.fetch_features_limit = limit
        return gpd.GeoDataFrame(
            {
                "entity_name": [f"school-{index}" for index in range(15)],
                "city": ["Tel Aviv"] * 15,
            },
            geometry=[Point(index, index) for index in range(15)],
            crs="EPSG:4326",
        )

    def describe_schema(self, layer):
        return LayerSchema(
            layer_id=layer.id,
            geometry_type="Point",
            fields=[
                LayerField(name="entity_name", type="string"),
                LayerField(name="city", type="string"),
            ],
        )

    def sample_field_values(self, layer, field, limit=20):
        return []


class CapturingLlm:
    def __init__(self):
        self.user = None

    def complete_json(self, system, user):
        self.user = json.loads(user)
        return {
            "description": " שכבת מוסדות חינוך לפי שם ועיר ",
            "tags": ["חינוך", "Education", "חינוך", "", 7],
            "_usage": {"total_tokens": 10},
        }


class CapturingMetadataGenerator:
    def __init__(self):
        self.source_url = None

    def generate(self, name, provider_name, source_url):
        self.source_url = source_url
        return GeneratedLayerMetadata(
            description="",
            dynamic_parameters=["fl:dynamic"],
            configurable_parameters=[
                LayerParameter(
                    name="fl:dynamic", type="string", required=True,
                    is_dynamic=True, configured_value="must-not-leak",
                ),
                LayerParameter(
                    name="environment", type="string", required=True,
                    options=["prod"], configured_value="must-not-leak",
                ),
            ],
        )


def test_generates_editable_metadata_from_ten_random_entities():
    providers = InMemoryProviderRegistry()
    sample_provider = SampleProvider()
    providers.register("sample", sample_provider)
    llm = CapturingLlm()

    result = LayerMetadataGenerator(llm, providers).generate(
        name="בתי ספר", provider_name="sample", source_url="sample://schools"
    )

    assert result.sample_count == 10
    assert len(llm.user["random_entity_sample"]) == 10
    assert all("geometry" not in row for row in llm.user["random_entity_sample"])
    assert llm.user["geometry_type"] == "Point"
    assert result.description == "שכבת מוסדות חינוך לפי שם ועיר"
    assert result.tags == ["חינוך", "Education"]
    # Must sample via a capped fetch, not the whole layer (see #4: MQS
    # layers can be huge — tagging must not trigger a full paginated fetch).
    assert sample_provider.fetch_features_limit == 100


def test_generates_metadata_from_known_cubes_request(tmp_path):
    rows = [{
        "netId": f"vehicle-{index}",
        "forceType": "ambulance",
        "eventTime": "2026-07-15T10:00:00Z",
        "geometry": f"POINT (34.{70 + index} 32.08)",
    } for index in range(10)]
    cubes, _ = make_cubes_provider(tmp_path, rows)
    providers = InMemoryProviderRegistry()
    providers.register("cubes", cubes)
    llm = CapturingLlm()

    result = LayerMetadataGenerator(llm, providers).generate(
        name="כוחות נעים", provider_name="cubes", source_url="transport"
    )

    fields = {field["name"] for field in llm.user["fields"]}
    assert {"netId", "forceType", "eventTime"} <= fields
    assert len(llm.user["random_entity_sample"]) == 10
    assert result.sample_count == 10


def test_cubes_metadata_discovers_dynamic_parameter_before_row_fetch(tmp_path):
    cubes, handler = make_cubes_provider(tmp_path, [])

    def metadata_only(request):
        handler.requests.append(request)
        assert request.method == "GET"
        assert request.extensions["timeout"]["read"] == 30
        return httpx.Response(200, json={
            "Name": "Our forces", "Description": "Moving forces",
            "Parameters": [{
                "Name": "TeamType", "IsRequired": True,
                "Role": "dynamic", "Type": "String",
            }],
            "Fields": [],
        })

    cubes._transport = httpx.MockTransport(metadata_only)
    providers = InMemoryProviderRegistry()
    providers.register("cubes", cubes)
    llm = CapturingLlm()

    result = LayerMetadataGenerator(llm, providers).generate(
        name="כוחות", provider_name="cubes", source_url="transport"
    )

    assert result.dynamic_parameters == ["TeamType"]
    assert result.sample_count == 0
    assert llm.user is None
    assert [request.method for request in handler.requests] == ["GET"]


def test_cubes_metadata_discovers_required_parameter_details_before_row_fetch(
    tmp_path,
):
    cubes, handler = make_cubes_provider(tmp_path, [])
    definitions = {
        "fl:dynamic": {
            "Name": "fl:dynamic", "IsRequired": True, "Type": "String",
        },
        "environment": {
            "Name": "environment", "IsRequired": True, "Type": "String",
            "Value": "prod",
            "Options": [{"Value": "prod", "Name": "Production"}],
        },
    }

    def metadata_only(request):
        handler.requests.append(request)
        path = request.url.path
        if path.endswith("/parameters"):
            return httpx.Response(200, json=list(definitions))
        if "/parameters/" in path:
            return httpx.Response(
                200, json=definitions[path.split("/parameters/", 1)[1]]
            )
        return httpx.Response(200, json={"Name": "Rasta", "Fields": []})

    cubes._transport = httpx.MockTransport(metadata_only)
    providers = InMemoryProviderRegistry()
    providers.register("cubes", cubes)
    llm = CapturingLlm()

    result = LayerMetadataGenerator(llm, providers).generate(
        name="Rasta", provider_name="cubes", source_url="rastaMoriaLand"
    )

    assert result.dynamic_parameters == ["fl:dynamic"]
    assert [item.name for item in result.configurable_parameters] == [
        "fl:dynamic", "environment",
    ]
    assert result.configurable_parameters[1].options == ["prod"]
    assert result.sample_count == 0
    assert llm.user is None
    assert all(request.method == "GET" for request in handler.requests)


def test_cubes_metadata_exposes_snake_case_required_parameter_before_row_fetch(
    tmp_path,
):
    cubes, handler = make_cubes_provider(tmp_path, [])

    def metadata_only(request):
        handler.requests.append(request)
        assert request.method == "GET"
        return httpx.Response(200, json={
            "name": "Operations",
            "parameters": [{
                "name": "environment", "is_required": True,
                "type": "String", "options": ["prod", "test"],
            }],
            "fields": [],
        })

    cubes._transport = httpx.MockTransport(metadata_only)
    providers = InMemoryProviderRegistry()
    providers.register("cubes", cubes)
    llm = CapturingLlm()

    result = LayerMetadataGenerator(llm, providers).generate(
        name="Operations", provider_name="cubes", source_url="operations"
    )

    assert [item.name for item in result.configurable_parameters] == [
        "environment",
    ]
    assert result.configurable_parameters[0].required is True
    assert result.configurable_parameters[0].options == ["prod", "test"]
    assert result.sample_count == 0
    assert llm.user is None
    assert [request.method for request in handler.requests] == ["GET"]


def test_new_metadata_generation_refreshes_changed_required_parameters(tmp_path):
    cubes, handler = make_cubes_provider(tmp_path, [])
    parameter_required = False

    def metadata_only(request):
        handler.requests.append(request)
        assert request.method == "GET"
        return httpx.Response(200, json={
            "Parameters": [{
                "Name": "tenant", "IsRequired": parameter_required,
                "Type": "String",
            }],
            "Fields": [],
        })

    cubes._transport = httpx.MockTransport(metadata_only)
    assert cubes.list_configurable_parameters(
        SimpleNamespace(id="preview", source_url="cubes://db/operations")
    ) == []

    parameter_required = True
    providers = InMemoryProviderRegistry()
    providers.register("cubes", cubes)
    llm = CapturingLlm()

    result = LayerMetadataGenerator(llm, providers).generate(
        name="Operations", provider_name="cubes", source_url="operations"
    )

    assert [item.name for item in result.configurable_parameters] == ["tenant"]
    assert result.sample_count == 0
    assert llm.user is None
    assert [request.method for request in handler.requests] == ["GET", "GET"]


def test_metadata_api_contract_persists_values_without_exposing_fixed_values():
    generator = CapturingMetadataGenerator()
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(layer_metadata_generator=generator)
        )
    )
    body = GenerateLayerMetadataRequest(
        name="Rasta",
        provider="cubes",
        source_url="rastaMoriaLand",
        cubes_parameters={"fl:dynamic": "9000", "environment": "prod"},
    )

    response = CatalogRouter.generate_metadata(body, request)

    assert generator.source_url == (
        "cubes://db/rastaMoriaLand?"
        "param_fl%3Adynamic=9000&param_environment=prod"
    )
    assert response.model_dump() == {
        "description": "",
        "tags": [],
        "sample_count": 0,
        "dynamic_parameters": ["fl:dynamic"],
        "configurable_parameters": [
            {
                "name": "fl:dynamic", "display_name": "",
                "required": True, "dynamic": True, "options": [],
            },
            {
                "name": "environment", "display_name": "",
                "required": True, "dynamic": False, "options": ["prod"],
            },
        ],
    }


def test_cubes_metadata_samples_main_route_after_dynamic_value_is_resolved(tmp_path):
    rows = [{
        "netId": f"force-{index}", "forceType": "vehicle",
        "geometry": f"POINT (34.{70 + index} 32.08)",
    } for index in range(10)]
    cubes, handler = make_cubes_provider(tmp_path, rows)

    def resolved_handler(request):
        handler.requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={
                "Parameters": [{
                    "Name": "TeamType", "IsRequired": True,
                    "Role": "dynamic", "Type": "String",
                }],
                "Fields": [{"Name": "netId", "Type": "String"}],
            })
        body = json.loads(request.content)
        assert body["TeamType"] == "our_forces"
        assert request.extensions["timeout"]["read"] == 60
        return httpx.Response(200, json=rows)

    cubes._transport = httpx.MockTransport(resolved_handler)
    providers = InMemoryProviderRegistry()
    providers.register("cubes", cubes)
    llm = CapturingLlm()

    result = LayerMetadataGenerator(llm, providers).generate(
        name="כוחות", provider_name="cubes",
        source_url="cubes://db/transport?param_TeamType=our_forces",
    )

    assert result.dynamic_parameters == ["TeamType"]
    assert result.sample_count == 10
    assert llm.user is not None


class MqsMetadataProvider:
    def __init__(self, include_business=True):
        self.include_business = include_business

    def fetch_features(self, layer, now=None, geometry=None, limit=None):
        data = {"triangle": ["A"], "clearence_level": [2]}
        if self.include_business:
            data.update({"שם": ["בית הכנסת הגדול"], "מהות": ["בית כנסת"]})
        return gpd.GeoDataFrame(data, geometry=[Point(34.8, 32.1)], crs="EPSG:4326")

    def describe_schema(self, layer):
        fields = [
            LayerField(name="triangle", type="string", metadata_relevant=False),
            LayerField(name="clearence_level", type="number", metadata_relevant=False),
        ]
        if self.include_business:
            fields.extend([
                LayerField(name="שם", type="string", samples=["בית הכנסת הגדול"]),
                LayerField(name="מהות", type="string", samples=["בית כנסת"]),
            ])
        return LayerSchema(layer_id=layer.id, geometry_type="Polygon", fields=fields)


def test_mqs_metadata_uses_only_property_list_business_fields():
    providers = InMemoryProviderRegistry()
    providers.register("mqs", MqsMetadataProvider())
    llm = CapturingLlm()

    LayerMetadataGenerator(llm, providers).generate(
        name="מקומות", provider_name="mqs", source_url="42"
    )

    assert {field["name"] for field in llm.user["fields"]} == {"שם", "מהות"}
    assert llm.user["random_entity_sample"] == [{
        "שם": "בית הכנסת הגדול", "מהות": "בית כנסת",
    }]


def test_mqs_metadata_fails_when_property_list_is_missing():
    providers = InMemoryProviderRegistry()
    providers.register("mqs", MqsMetadataProvider(include_business=False))

    with pytest.raises(ProviderError, match="property_list fields were not found"):
        LayerMetadataGenerator(CapturingLlm(), providers).generate(
            name="מקומות", provider_name="mqs", source_url="42"
        )


def test_mqs_upstream_500_from_generate_metadata_is_diagnostic_502(tmp_path):
    store = RuntimeSettingsStore(Settings(
        _env_file=None,
        runtime_settings_file=str(tmp_path / "runtime-settings.json"),
        mqs_base_url="https://mqs.test",
    ))
    mqs = MqsProvider(store, httpx.MockTransport(
        lambda request: httpx.Response(500, json={"error": "MQS failed"})
    ))
    providers = InMemoryProviderRegistry()
    providers.register("mqs", mqs)
    app = FastAPI()
    _register_error_handlers(app)
    app.include_router(catalog_router.router)
    app.state.layer_metadata_generator = LayerMetadataGenerator(
        CapturingLlm(), providers
    )

    response = TestClient(app, raise_server_exceptions=False).post(
        "/api/layers/generate-metadata",
        json={"name": "Places", "provider": "mqs", "source_url": "42"},
    )

    assert response.status_code == 502
    assert "upstream returned 500" in response.json()["detail"]
    assert "User_ID is not configured" in response.json()["detail"]
