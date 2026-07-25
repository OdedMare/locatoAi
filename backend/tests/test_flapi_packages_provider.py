import json
from typing import List
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from flunks.flow_models import FailedQuery, FlowResults, MetaData
from shapely.geometry import box

from app.bl.catalog.models.layer_meta import LayerMeta
from app.common.config.settings import Settings
from app.common.errors.provider_error import ProviderError
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.providers.flapi.package_gateway import FlowPackageGateway
from app.dal.providers.flapi.package_metadata import FlowPackageMetadata
from app.dal.providers.flapi.package_serializer import FlowPackageSerializer
from app.dal.providers.flapi.provider import FlapiProvider
from app.dal.providers.flapi.source import FlapiSource
from app.service.catalog.router import CatalogRouter


class DefinitionsHandler:
    """Mock transport for the GET /package/v1/quick/{id} discovery call only."""

    def __init__(self, definitions):
        self.definitions = definitions
        self.requests: List[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(
            200, json={"466192": {"Parameters": self.definitions}}
        )


def flow_results(results=None, partial=False, failed_queries=None, limited=None):
    results = results if results is not None else {"FinalCube": [{
        "id": "result-1",
        "eventTime": "2026-07-24T10:00:00Z",
        "geometry": "POINT (34.8 32.1)",
    }]}
    return FlowResults(
        metadata=MetaData(
            isPartialSuccess=partial,
            traceId="trace-1",
            queriesReachedResultsLimit=limited or [],
            partialSuccessFailedQueries=failed_queries or [],
        ),
        results=results,
    )


def make_provider(tmp_path, definitions_handler, runner_factory=None, monkeypatch=None):
    store = RuntimeSettingsStore(Settings(
        _env_file=None,
        runtime_settings_file=str(tmp_path / "runtime-settings.json"),
        cubes_base_url="https://flapi.test",
        cubes_token="jwt",
        flapi_username="oded",
    ))
    provider = FlapiProvider(store, httpx.MockTransport(definitions_handler))
    if runner_factory is not None:
        monkeypatch.setattr(
            "app.dal.providers.flapi.package_gateway.FlunksRunner",
            runner_factory,
        )
    return provider


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
        package_input_parameter="Terms",
        package_output_fields=["identifier", "feature_score"],
    )


class StubRunner:
    """Captures FlunksRunner construction args and returns a canned FlowResults."""

    last_instance = None

    def __init__(self, flapi_config, package_config, flunks_config=None,
                 exceptions_config=None):
        self.flapi_config = flapi_config
        self.package_config = package_config
        self.flunks_config = flunks_config
        self.exceptions_config = exceptions_config
        self.success_chunks = 1
        self.failed_chunks = 0
        self.result = flow_results()
        StubRunner.last_instance = self

    def run(self):
        return self.result


def test_flapi_package_discovers_serializes_executes_and_maps_rows(
    tmp_path, monkeypatch
):
    definitions_handler = DefinitionsHandler(definitions())
    provider = make_provider(
        tmp_path, definitions_handler, StubRunner, monkeypatch
    )
    boundary = box(34.7, 32.0, 34.9, 32.2)

    features = provider.fetch_features(
        package_layer(configured_source()), geometry=boundary
    )

    assert list(features["id"]) == ["result-1"]
    assert list(features["_package_query"]) == ["FinalCube"]
    assert features.iloc[0].geometry.x == 34.8
    get_request = definitions_handler.requests[0]
    assert get_request.url.path == "/package/v1/quick/466192"

    runner = StubRunner.last_instance
    assert runner.flapi_config.username == "oded"
    assert runner.flapi_config.token == "jwt"
    assert runner.package_config.package_id == "466192"
    assert runner.package_config.output_cube.cube_name == "FinalCube"
    assert runner.package_config.output_cube.cube_fields == [
        "identifier", "feature_score",
    ]
    assert runner.package_config.main_input_cube.cube_name == "Terms"
    assert runner.package_config.main_input_cube.values == ["alpha", "beta"]
    assert runner.package_config.static_parameters == {
        "MinScore": {"Name": "1", "Value": 1},
        "Enabled": "False",
        "Area": boundary.wkt,
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


def test_package_defaults_to_last_queries(tmp_path, monkeypatch):
    definitions_handler = DefinitionsHandler([{
        "Name": "Enabled", "IsRequired": True,
        "Type": "Boolean", "Value": "False",
    }])
    provider = make_provider(
        tmp_path, definitions_handler, StubRunner, monkeypatch
    )

    provider.fetch_features(package_layer("flapi://package/466192"))

    runner = StubRunner.last_instance
    assert runner.package_config.static_parameters == {"Enabled": "False"}


def test_package_rejects_missing_required_parameter_before_execution(
    tmp_path, monkeypatch
):
    definitions_handler = DefinitionsHandler([{
        "Name": "Tenant", "IsRequired": True, "Type": "String",
    }])
    provider = make_provider(
        tmp_path, definitions_handler, StubRunner, monkeypatch
    )

    with pytest.raises(ProviderError, match="Tenant.*required"):
        provider.fetch_features(package_layer("flapi://package/466192"))

    assert StubRunner.last_instance is None
    assert [request.method for request in definitions_handler.requests] == ["GET"]


def test_package_reports_flunks_chunk_statistics(tmp_path, monkeypatch):
    definitions_handler = DefinitionsHandler([{
        "Name": "Enabled", "IsRequired": True,
        "Type": "Boolean", "Value": "False",
    }])
    provider = make_provider(
        tmp_path, definitions_handler, StubRunner, monkeypatch
    )

    provider.fetch_features(package_layer("flapi://package/466192"))

    gateway = provider._package._gateway
    assert gateway.success_chunks == 1
    assert gateway.failed_chunks == 0


def test_package_surfaces_cube_errors_from_flow_results(tmp_path, monkeypatch):
    definitions_handler = DefinitionsHandler([{
        "Name": "Enabled", "IsRequired": True,
        "Type": "Boolean", "Value": "False",
    }])

    def failing_runner(flapi_config, package_config, flunks_config=None,
                        exceptions_config=None):
        runner = StubRunner(
            flapi_config, package_config, flunks_config, exceptions_config
        )
        runner.result = flow_results(
            failed_queries=[FailedQuery(
                id="1", name="FinalCube", uniqueName="FinalCube#1",
            )],
        )
        return runner

    provider = make_provider(
        tmp_path, definitions_handler, failing_runner, monkeypatch
    )

    features = provider.fetch_features(package_layer("flapi://package/466192"))
    assert list(features["id"]) == ["result-1"]


def test_package_source_persists_typed_json_inputs():
    source = configured_source()
    query = parse_qs(urlsplit(source).query)

    assert source.startswith("flapi://package/466192?")
    assert json.loads(query["input_MinScore"][0]) == "1"
    assert json.loads(query["input_StartTime"][0]) == {
        "TimeBackUnit": "minute", "TimeBackValue": 15,
    }


def test_package_source_persists_input_parameter_and_output_fields():
    source = configured_source()
    layer = package_layer(source)
    parsed_source = FlapiSource()

    assert parsed_source.package_input_parameter(layer) == "Terms"
    assert parsed_source.package_output_fields(layer) == [
        "identifier", "feature_score",
    ]


def test_package_input_cube_uses_explicit_time_parameter():
    serializer = FlowPackageSerializer(FlowPackageMetadata())
    input_cube = serializer.build_input_cube(
        definitions(), {}, temporal_range=("2026-01-01T00:00:00Z", "2026-04-01T00:00:00Z"),
        input_parameter="StartTime",
    )

    assert input_cube.cube_name == "StartTime"
    assert input_cube.start_time is not None
    assert input_cube.end_time is not None
    assert input_cube.values == []


def test_package_validates_absolute_time_and_unknown_types():
    serializer = FlowPackageSerializer(FlowPackageMetadata())
    time_definition = [{
        "Name": "Window", "Type": "DateTime",
        "OntologyType": "Time", "IsRequired": True,
    }]
    assert serializer.build_static_parameters(time_definition, {"Window": {
        "From": "2024-11-26T00:00:00.000Z",
        "To": "2024-11-26T23:59:59.000Z",
    }})["Window"]["To"].endswith("Z")

    with pytest.raises(ProviderError, match="timezone"):
        serializer.build_static_parameters(time_definition, {"Window": {
            "From": "2024-11-26T00:00:00",
            "To": "2024-11-26T23:59:59",
        }})

    custom = {"nested": ["kept", 7]}
    assert serializer.build_static_parameters(
        [{"Name": "Custom", "Type": "FutureType"}],
        {"Custom": custom},
    ) == {"Custom": custom}


def test_package_emits_geometry_as_wkt_and_time_as_json():
    serializer = FlowPackageSerializer(FlowPackageMetadata())
    body = serializer.build_static_parameters(definitions(), {
        "Terms": ["alpha"],
        "MinScore": 1,
        "Enabled": "True",
        "Area": {"value": "POINT (34.8 32.1)"},
        "StartTime": '{"TimeBackUnit":"hour","TimeBackValue":2}',
    })

    assert body["Area"] == "POINT (34.8 32.1)"
    assert body["StartTime"] == {
        "TimeBackUnit": "hour", "TimeBackValue": 2,
    }


def test_package_execution_options_are_validated():
    source = FlapiSource()
    layer = package_layer(
        "flapi://package/466192?"
        "allQueries=true&executeContinuedProcess=false&isPartialSuccess=true"
    )

    assert source.execution_params(layer) == [
        ("allQueries", "true"),
        ("executeContinuedProcess", "false"),
        ("isPartialSuccess", "true"),
    ]

    with pytest.raises(ProviderError, match="allQueries.*true or false"):
        source.execution_params(package_layer(
            "flapi://package/466192?allQueries=yes"
        ))


def test_package_metadata_accepts_identifier_to_definition_map():
    metadata = FlowPackageMetadata()
    payload = {"466192": {
        "first": {"Name": "Tenant", "Type": "String"},
        "second": {"Name": "Window", "OntologyType": "Time"},
    }}

    assert [item["Name"] for item in metadata.definitions(payload)] == [
        "Tenant", "Window",
    ]


def test_package_requires_flapi_username(tmp_path):
    store = RuntimeSettingsStore(Settings(
        _env_file=None,
        runtime_settings_file=str(tmp_path / "runtime-settings.json"),
        cubes_base_url="https://flapi.test",
        cubes_token="jwt",
    ))
    provider = FlapiProvider(
        store, httpx.MockTransport(DefinitionsHandler([]))
    )

    with pytest.raises(ProviderError, match="flapi_username"):
        provider.fetch_features(package_layer("flapi://package/466192"))
