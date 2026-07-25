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


def package_records():
    return [{
        "id": "result-1",
        "eventTime": "2026-07-24T10:00:00Z",
        "geometry": "POINT (34.8 32.1)",
    }]


def make_provider(tmp_path, runner_factory=None, monkeypatch=None):
    """Builds the provider with flunks' runner stubbed out.

    flunks owns every FLAPI HTTP call, so there is no transport to mock —
    substituting FlunksRunner is the only seam the package path needs.
    """
    store = RuntimeSettingsStore(Settings(
        _env_file=None,
        runtime_settings_file=str(tmp_path / "runtime-settings.json"),
        cubes_base_url="https://flapi.test",
        cubes_token="jwt",
        flapi_username="oded",
    ))
    if runner_factory is not None:
        monkeypatch.setattr(
            "app.dal.providers.flapi.package_gateway.FlunksRunner",
            runner_factory,
        )
    return FlapiProvider(store)


def package_layer(source_url):
    return LayerMeta(
        id="package-layer", name="Workflow", provider="flapi",
        source_url=source_url,
    )


def configured_source():
    return CatalogRouter.normalized_source(
        "flapi", "466192",
        package_query="FinalCube",
        package_input_cube_name="RawInput",
        package_input_cube_parameter="TimeRange",
        package_input_cube_kind="time",
        package_output_cube_name="הכנסה - 👑",
    )


def geo_source():
    return CatalogRouter.normalized_source(
        "flapi", "466192",
        package_input_cube_name="RawInput",
        package_input_cube_parameter="GeoQuery",
        package_input_cube_kind="geo",
        package_output_cube_name="FinalCube",
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
    provider = make_provider(tmp_path, StubRunner, monkeypatch)
    boundary = box(34.7, 32.0, 34.9, 32.2)

    features = provider.fetch_features(
        package_layer(configured_source()), geometry=boundary,
        temporal_range=("2026-07-18T00:00:00Z", "2026-07-18T03:00:00Z"),
    )

    assert list(features["id"]) == ["result-1"]
    assert list(features["_package_query"]) == ["הכנסה - 👑"]
    assert features.iloc[0].geometry.x == 34.8

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


def test_geo_input_cube_passes_query_boundary_polygons_as_wkt(
    tmp_path, monkeypatch
):
    provider = make_provider(tmp_path, StubRunner, monkeypatch)
    boundary = box(34.7, 32.0, 34.9, 32.2)

    provider.fetch_features(package_layer(geo_source()), geometry=boundary)

    runner = StubRunner.last_instance
    input_cube = runner.package_config.main_input_cube
    assert input_cube.cube_name == "RawInput"
    assert input_cube.cube_parameter == "GeoQuery"
    assert len(input_cube.values) == 1
    assert input_cube.values[0].startswith("MULTIPOLYGON")
    assert runner.package_config.output_cube.cube_name == "FinalCube"


def test_geo_input_cube_wkt_round_trips_to_query_boundary(tmp_path, monkeypatch):
    from shapely import wkt

    provider = make_provider(tmp_path, StubRunner, monkeypatch)
    boundary = box(34.7, 32.0, 34.9, 32.2)

    provider.fetch_features(package_layer(geo_source()), geometry=boundary)

    input_cube = StubRunner.last_instance.package_config.main_input_cube
    parsed = wkt.loads(input_cube.values[0])
    assert parsed.equals(boundary)


def test_geo_source_persists_kind():
    layer = package_layer(geo_source())
    assert FlapiSource.package_input_cube_kind(layer) == "geo"


def test_package_reports_flunks_chunk_statistics(tmp_path, monkeypatch):
    provider = make_provider(tmp_path, StubRunner, monkeypatch)

    provider.fetch_features(package_layer(configured_source()))

    gateway = provider._package._gateway
    assert gateway.success_chunks == 1
    assert gateway.failed_chunks == 0


def test_package_ignores_non_dict_records(tmp_path, monkeypatch):

    def mixed_runner(flapi_config, package_config, flunks_config=None,
                     exceptions_config=None):
        runner = StubRunner(
            flapi_config, package_config, flunks_config, exceptions_config
        )
        runner.result = ["not-a-dict"] + package_records()
        return runner

    provider = make_provider(
        tmp_path, mixed_runner, monkeypatch
    )

    features = provider.fetch_features(package_layer(configured_source()))
    assert list(features["id"]) == ["result-1"]


def test_package_rejects_non_list_response(tmp_path, monkeypatch):

    def object_runner(flapi_config, package_config, flunks_config=None,
                      exceptions_config=None):
        runner = StubRunner(
            flapi_config, package_config, flunks_config, exceptions_config
        )
        runner.result = {"unexpected": "shape"}
        return runner

    provider = make_provider(
        tmp_path, object_runner, monkeypatch
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
    assert parsed_source.package_input_cube_kind(layer) == "time"
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


def test_geo_input_cube_combines_polygons_into_one_multipolygon():
    from shapely import wkt as shapely_wkt
    from shapely.geometry import MultiPolygon

    serializer = FlowPackageSerializer()
    boundary = MultiPolygon([box(34.7, 32.0, 34.8, 32.1), box(35.0, 32.4, 35.1, 32.5)])

    input_cube = serializer.build_input_cube(
        "שכבה גיאוגרפית", "שכבה גיאוגרפית", kind="geo", geometry=boundary,
    )

    # One geographic layer is one identifier, so both polygons share a single
    # MULTIPOLYGON rather than becoming two chunks.
    assert len(input_cube.values) == 1
    assert input_cube.values[0].startswith("MULTIPOLYGON")
    assert input_cube.start_time is None and input_cube.end_time is None
    assert shapely_wkt.loads(input_cube.values[0]).equals(boundary)


def test_geo_input_cube_without_geometry_is_empty():
    serializer = FlowPackageSerializer()

    input_cube = serializer.build_input_cube(
        "שכבה גיאוגרפית", "שכבה גיאוגרפית", kind="geo",
    )

    assert input_cube.values == []


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
    provider = make_provider(tmp_path, StubRunner, monkeypatch)
    source = CatalogRouter.normalized_source(
        "flapi", "466192",
        package_input_cube_name="RawInput",
        package_input_cube_parameter="TimeRange",
    )

    with pytest.raises(ProviderError, match="output cube name"):
        provider.fetch_features(package_layer(source))


def test_package_requires_flapi_username(tmp_path):
    store = RuntimeSettingsStore(Settings(
        _env_file=None,
        runtime_settings_file=str(tmp_path / "runtime-settings.json"),
        cubes_base_url="https://flapi.test",
        cubes_token="jwt",
    ))

    with pytest.raises(ProviderError, match="flapi_username"):
        FlapiProvider(store).fetch_features(package_layer(configured_source()))
