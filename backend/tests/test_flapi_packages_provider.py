import json
from typing import List
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from shapely.geometry import box

from app.bl.catalog.models.layer_meta import LayerMeta
from app.common.config.settings import Settings
from app.common.errors.provider_error import ProviderError
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.providers.flapi.package_metadata import FlowPackageMetadata
from app.dal.providers.flapi.package_serializer import FlowPackageSerializer
from app.dal.providers.flapi.provider import FlapiProvider
from app.service.catalog.router import CatalogRouter


class PackageHandler:
    def __init__(self, definitions, results=None):
        self.definitions = definitions
        self.results = results or [{
            "id": "result-1",
            "eventTime": "2026-07-24T10:00:00Z",
            "geometry": "POINT (34.8 32.1)",
        }]
        self.requests: List[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.method == "GET":
            return httpx.Response(
                200, json={"466192": {"Parameters": self.definitions}}
            )
        return httpx.Response(200, json={
            "metadata": {
                "isPartialSuccess": False,
                "traceId": "trace-1",
                "queriesReachedResultsLimit": [],
                "partialSuccessFailedQueries": [],
            },
            "results": {"FinalCube": self.results},
        })


def make_provider(tmp_path, handler):
    store = RuntimeSettingsStore(Settings(
        _env_file=None,
        runtime_settings_file=str(tmp_path / "runtime-settings.json"),
        cubes_base_url="https://flapi.test",
        cubes_token="jwt",
        flapi_username="oded",
    ))
    return FlapiProvider(store, httpx.MockTransport(handler))


def package_layer(source_url):
    return LayerMeta(
        id="package-layer", name="Workflow", provider="flapi",
        source_url=source_url,
    )


def definitions():
    return [
        {
            "Name": "Terms", "DisplayName": "Search terms",
            "IsRequired": True, "IsSingleValue": False, "Type": "String",
        },
        {
            "Name": "MinScore", "IsRequired": True,
            "IsSingleValue": True, "Type": "Number",
        },
        {
            "Name": "Enabled", "IsRequired": True,
            "IsSingleValue": True, "Type": "Boolean",
        },
        {
            "Name": "Area", "IsRequired": True,
            "IsSingleValue": True, "Type": "Geometry",
        },
        {
            "Name": "StartTime", "IsRequired": True,
            "IsSingleValue": True, "Type": "DateTime",
            "OntologyType": "Time",
        },
    ]


def configured_source():
    return CatalogRouter.normalized_source(
        "flapi", "466192",
        flapi_resource_type="package",
        package_parameters={
            "Terms": ["alpha", "beta"],
            "MinScore": "1",
            "Enabled": "False",
            "StartTime": {
                "TimeBackUnit": "minute",
                "TimeBackValue": 15,
            },
        },
        package_query="FinalCube",
    )


def test_flapi_package_discovers_serializes_executes_and_maps_rows(tmp_path):
    handler = PackageHandler(definitions())
    provider = make_provider(tmp_path, handler)
    boundary = box(34.7, 32.0, 34.9, 32.2)

    features = provider.fetch_features(
        package_layer(configured_source()), geometry=boundary
    )

    assert list(features["id"]) == ["result-1"]
    assert list(features["_package_query"]) == ["FinalCube"]
    assert features.iloc[0].geometry.x == 34.8
    get_request, post_request = handler.requests
    assert get_request.url.path == "/package/v1/quick/466192"
    assert post_request.url.path == "/package/v3/466192"
    assert post_request.url.params.get_list("queries") == ["FinalCube"]
    assert post_request.headers["Authorization"] == "Bearer jwt"
    assert post_request.headers["username"] == "oded"
    assert json.loads(post_request.content) == {
        "Terms": [
            {"Name": "alpha", "Value": "alpha"},
            {"Name": "beta", "Value": "beta"},
        ],
        "MinScore": {"Name": "1", "Value": 1},
        "Enabled": "False",
        "Area": {"value": boundary.wkt},
        "StartTime": {
            "TimeBackUnit": "minute",
            "TimeBackValue": 15,
        },
    }
    schema = provider.describe_schema(package_layer(configured_source()))
    assert schema.temporal_field == "eventTime"
    assert {field.name for field in schema.fields} >= {
        "id", "eventTime", "_package_query",
    }


def test_package_defaults_to_last_queries(tmp_path):
    handler = PackageHandler([{
        "Name": "Enabled", "IsRequired": True,
        "Type": "Boolean", "Value": "False",
    }])
    provider = make_provider(tmp_path, handler)

    provider.fetch_features(package_layer("flapi://package/466192"))

    post_request = handler.requests[-1]
    assert post_request.url.params["lastQueries"] == "true"
    assert json.loads(post_request.content) == {"Enabled": "False"}


def test_package_rejects_missing_required_parameter_before_execution(tmp_path):
    handler = PackageHandler([{
        "Name": "Tenant", "IsRequired": True, "Type": "String",
    }])
    provider = make_provider(tmp_path, handler)

    with pytest.raises(ProviderError, match="Tenant.*required"):
        provider.fetch_features(package_layer("flapi://package/466192"))

    assert [request.method for request in handler.requests] == ["GET"]


def test_package_source_persists_typed_json_inputs():
    source = configured_source()
    query = parse_qs(urlsplit(source).query)

    assert source.startswith("flapi://package/466192?")
    assert json.loads(query["input_MinScore"][0]) == "1"
    assert json.loads(query["input_StartTime"][0]) == {
        "TimeBackUnit": "minute", "TimeBackValue": 15,
    }


def test_package_validates_absolute_time_and_unknown_types():
    serializer = FlowPackageSerializer(FlowPackageMetadata())
    time_definition = [{
        "Name": "Window", "Type": "DateTime",
        "OntologyType": "Time", "IsRequired": True,
    }]
    assert serializer.build(time_definition, {"Window": {
        "From": "2024-11-26T00:00:00.000Z",
        "To": "2024-11-26T23:59:59.000Z",
    }})["Window"]["To"].endswith("Z")

    with pytest.raises(ProviderError, match="timezone"):
        serializer.build(time_definition, {"Window": {
            "From": "2024-11-26T00:00:00",
            "To": "2024-11-26T23:59:59",
        }})

    custom = {"nested": ["kept", 7]}
    assert serializer.build(
        [{"Name": "Custom", "Type": "FutureType"}],
        {"Custom": custom},
    ) == {"Custom": custom}
