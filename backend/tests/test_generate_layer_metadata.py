import json

import geopandas as gpd
import httpx
import pytest
from shapely.geometry import Point

from app.bl.agent.generate_layer_metadata.layer_metadata_generator import (
    LayerMetadataGenerator,
)
from app.bl.ports.layer_field import LayerField
from app.bl.ports.layer_schema import LayerSchema
from app.dal.providers.registry import InMemoryProviderRegistry
from app.common.errors.provider_error import ProviderError
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
