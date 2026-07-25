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


def package_records():
    return [{
        "id": "result-1",
        "eventTime": "2026-07-24T10:00:00Z",
        "geometry": "POINT (34.8 32.1)",
    }]


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
            "Name": "StartTime", "IsRequired": True,
            "IsSingleValue": True, "Type": "DateTime",
            "OntologyType": "Time",
        },
    ]


def configured_source():
    return CatalogRouter.normalized_source(
        "flapi", "466192",
        package_query="FinalCube",
        package_input_cube_name="RawInput",
        package_input_cube_parameter="TimeRange",
        package_output_cube_name="הכנסה - 👑",
    )


class StubRunner:
    """Captures FlunksRunner construction args and returns canned records."""

    last_instance = None

    def __init__(self, flapi_config, package_config, flunks_config=None,
                 exceptions_config=None):
        self.flapi_config = flapi_config
        self.package_config = package_config
        self.flunks_config = flunks_config
        self.exceptions_config = exceptions_config
        self.success_chunks = 1
        self.failed_chunks = 0
        self.result = package_records()
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
        package_layer(configured_source()), geometry=boundary,
        temporal_range=("2026-07-18T00:00:00Z", "2026-07-18T03:00:00Z"),
    )

    assert list(features["id"]) == ["result-1"]
    assert list(features["_package_query"]) == ["הכנסה - 👑"]
    assert features.iloc[0].geometry.x == 34.8
    get_request = definitions_handler.requests[0]
    assert get_request.url.path == "/package/v1/quick/466192"

    runner = StubRunner.last_instance
    assert runner.flapi_config.username == "oded"
    assert runner.flapi_config.token == "jwt"
    assert runner.package_config.package_id == "466192"
    assert runner.package_config.output_cube.cube_name == "הכנסה - 👑"
    assert runner.package_config.main_input_cube.cube_name == "RawInput"
    assert runner.package_config.main_input_cube.cube_parameter == "TimeRange"
    assert runner.package_config.main_input_cube.start_time.isoformat() == (
        "2026-07-18T00:00:00+00:00"
    )
    assert runner.package_config.main_input_cube.end_time.isoformat() == (
        "2026-07-18T03:00:00+00:00"
    )

    schema = provider.describe_schema(package_layer(configured_source()))
    assert schema.temporal_field == "eventTime"
    assert {field.name for field in schema.fields} >= {
        "id", "eventTime", "_package_query",
    }


def test_package_reports_flunks_chunk_statistics(tmp_path, monkeypatch):
    definitions_handler = DefinitionsHandler(definitions())
    provider = make_provider(
        tmp_path, definitions_handler, StubRunner, monkeypatch
    )

    provider.fetch_features(package_layer(configured_source()))

    gateway = provider._package._gateway
    assert gateway.success_chunks == 1
    assert gateway.failed_chunks == 0


def test_package_ignores_non_dict_records(tmp_path, monkeypatch):
    definitions_handler = DefinitionsHandler(definitions())

    def mixed_runner(flapi_config, package_config, flunks_config=None,
                     exceptions_config=None):
        runner = StubRunner(
            flapi_config, package_config, flunks_config, exceptions_config
        )
        runner.result = ["not-a-dict"] + package_records()
        return runner

    provider = make_provider(
        tmp_path, definitions_handler, mixed_runner, monkeypatch
    )

    features = provider.fetch_features(package_layer(configured_source()))
    assert list(features["id"]) == ["result-1"]


def test_package_rejects_non_list_response(tmp_path, monkeypatch):
    definitions_handler = DefinitionsHandler(definitions())

    def object_runner(flapi_config, package_config, flunks_config=None,
                      exceptions_config=None):
        runner = StubRunner(
            flapi_config, package_config, flunks_config, exceptions_config
        )
        runner.result = {"unexpected": "shape"}
        return runner

    provider = make_provider(
        tmp_path, definitions_handler, object_runner, monkeypatch
    )

    with pytest.raises(ProviderError, match="not a list"):
        provider.fetch_features(package_layer(configured_source()))


def test_package_source_persists_cube_names():
    source = configured_source()
    layer = package_layer(source)
    parsed_source = FlapiSource()

    assert source.startswith("flapi://package/466192?")
    assert parsed_source.package_input_cube_name(layer) == "RawInput"
    assert parsed_source.package_input_cube_parameter(layer) == "TimeRange"
    assert parsed_source.package_output_cube_name(layer) == "הכנסה - 👑"


def test_input_cube_uses_explicit_temporal_range():
    serializer = FlowPackageSerializer()
    input_cube = serializer.build_input_cube(
        "RawInput", "TimeRange",
        temporal_range=("2026-01-01T00:00:00Z", "2026-04-01T00:00:00Z"),
    )

    assert input_cube.cube_name == "RawInput"
    assert input_cube.cube_parameter == "TimeRange"
    assert input_cube.start_time.isoformat() == "2026-01-01T00:00:00+00:00"
    assert input_cube.end_time.isoformat() == "2026-04-01T00:00:00+00:00"


def test_input_cube_requires_names():
    serializer = FlowPackageSerializer()
    with pytest.raises(ProviderError, match="input cube name"):
        serializer.build_input_cube(None, "TimeRange")
    with pytest.raises(ProviderError, match="input cube parameter"):
        serializer.build_input_cube("RawInput", None)


def test_input_cube_defaults_time_window_when_range_absent():
    from datetime import datetime, timezone

    serializer = FlowPackageSerializer()
    now = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)
    input_cube = serializer.build_input_cube(
        "RawInput", "TimeRange", now=now,
    )

    assert input_cube.end_time == now
    assert input_cube.start_time == datetime(
        2026, 7, 25, 11, 0, tzinfo=timezone.utc
    )


def test_package_output_cube_name_required_at_execution(tmp_path, monkeypatch):
    definitions_handler = DefinitionsHandler(definitions())
    provider = make_provider(
        tmp_path, definitions_handler, StubRunner, monkeypatch
    )
    source = CatalogRouter.normalized_source(
        "flapi", "466192",
        package_input_cube_name="RawInput",
        package_input_cube_parameter="TimeRange",
    )

    with pytest.raises(ProviderError, match="output cube name"):
        provider.fetch_features(package_layer(source))


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
        provider.fetch_features(package_layer(configured_source()))
