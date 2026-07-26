import json

import geopandas as gpd
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from shapely.geometry import Point

from app.bl.agent.generate_layer_metadata.layer_metadata_generator import (
    LayerMetadataGenerator,
)
from app.bl.catalog.models.layer_field import LayerField
from app.bl.catalog.models.layer_schema import LayerSchema
from app.common.config.settings import Settings
from app.common.errors.provider_error import ProviderError
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.providers.mqs.provider import MqsProvider
from app.dal.providers.registry import InMemoryProviderRegistry
from app.main import _register_error_handlers
from app.service.catalog import router as catalog_router


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
