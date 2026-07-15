import json
from typing import List, Optional

import httpx
import pytest
from shapely.geometry import box

from app.bl.ports import LayerMeta
from app.common.config import Settings
from app.common.errors import ProviderError
from app.common.runtime_settings import RuntimeSettingsStore
from app.dal.providers.cubes import CubesProvider, cubes_database_name


class RecordingHandler:
    def __init__(self, payload):
        self.payload = payload
        self.requests: List[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, json=self.payload)


def make_provider(tmp_path, payload, base_url="https://cubes.test", token="jwt"):
    store = RuntimeSettingsStore(Settings(
        _env_file=None,
        runtime_settings_file=str(tmp_path / "runtime-settings.json"),
        cubes_base_url=base_url,
        cubes_token=token,
    ))
    handler = RecordingHandler(payload)
    return CubesProvider(store, httpx.MockTransport(handler)), handler


def layer(source_url="cubes://db/transport"):
    return LayerMeta(
        id="cube-layer", name="אוטובוסים", provider="cubes",
        source_url=source_url,
    )


def record(identifier="bus-1", geometry="POINT (34.78 32.08)"):
    return {
        "zonesString": "north",
        "eventTime": "2026-07-15T10:00:00Z",
        "arriveTime": "2026-07-15T10:01:00Z",
        "forceType": "bus",
        "callSign": "5",
        "unit": "public-transport",
        "netId": "net-1",
        "pstn": "123",
        "sourceType": "gps",
        "id": identifier,
        "geometry": geometry,
    }


def test_database_name_parsing():
    assert cubes_database_name(layer()) == "transport"
    assert cubes_database_name(layer("transport")) == "transport"
    assert cubes_database_name(layer("https://host/cube/v1/transport")) == "transport"


def test_posts_query_and_preserves_all_fields(tmp_path):
    provider, handler = make_provider(tmp_path, [record()])
    features = provider.fetch_features(layer())

    assert len(features) == 1
    assert features.iloc[0]["id"] == "bus-1"
    assert features.iloc[0]["callSign"] == "5"
    assert features.iloc[0].geometry.x == 34.78
    request = handler.requests[0]
    assert request.method == "POST"
    assert request.url.path == "/cube/v1/transport"
    assert request.headers["Authorization"] == "jwt"
    body = json.loads(request.content)
    assert body["eventTime"] == {"TimeBackUnit": "hour", "TimeBackValue": 1}
    assert "Location" not in body["arriveTime.not"]


def test_pushes_boundary_as_wkt_location(tmp_path):
    provider, handler = make_provider(tmp_path, {"data": [record()]})
    boundary = box(34.7, 32.0, 34.9, 32.2)
    provider.fetch_features(layer(), geometry=boundary)
    body = json.loads(handler.requests[0].content)
    assert body["arriveTime.not"]["Location"] == boundary.wkt


def test_schema_declares_event_time_and_point_geometry(tmp_path):
    provider, handler = make_provider(tmp_path, [record()])
    schema = provider.describe_schema(layer())
    assert schema.geometry_type == "Point"
    assert schema.temporal_field == "eventTime"
    assert {field.name for field in schema.fields} >= {"id", "callSign", "eventTime"}
    assert len(handler.requests) == 1


def test_schema_is_inferred_generically_and_cached_after_fetch(tmp_path):
    row = record()
    row["newNumericField"] = 17
    row["newBooleanField"] = True
    row["futureSchemaField"] = "works-without-code-change"
    provider, handler = make_provider(tmp_path, [row])

    provider.fetch_features(layer())
    schema = provider.describe_schema(layer())
    fields = {field.name: field for field in schema.fields}
    assert fields["newNumericField"].type == "number"
    assert fields["newBooleanField"].type == "boolean"
    assert fields["futureSchemaField"].samples == ["works-without-code-change"]
    assert "geometry" not in fields
    assert len(handler.requests) == 1  # describe_schema reused the fetch cache


def test_sample_field_values(tmp_path):
    provider, _ = make_provider(tmp_path, [
        record("bus-1"), record("bus-2"), record("bus-1")
    ])
    assert provider.sample_field_values(layer(), "id") == ["bus-1", "bus-2"]


def test_skips_invalid_or_non_point_geometry(tmp_path):
    provider, _ = make_provider(tmp_path, [
        record("bad", "not-wkt"), record("line", "LINESTRING (0 0, 1 1)"),
    ])
    assert provider.fetch_features(layer()).empty


def test_missing_configuration_fails_clearly(tmp_path):
    provider, _ = make_provider(tmp_path, [], base_url=None)
    with pytest.raises(ProviderError, match="base URL"):
        provider.fetch_features(layer())
    provider, _ = make_provider(tmp_path, [], token="")
    with pytest.raises(ProviderError, match="token"):
        provider.fetch_features(layer())
