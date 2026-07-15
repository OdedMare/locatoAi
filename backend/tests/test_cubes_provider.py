import json
from typing import List, Optional

import httpx
import pytest
from shapely import wkt
from shapely.geometry import box

from app.bl.ports.layer_meta import LayerMeta
from app.common.config import Settings
from app.common.errors.provider_error import ProviderError
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.providers.cubes import CubesProvider, cubes_database_name


class RecordingHandler:
    def __init__(self, payload):
        self.payload = payload
        self.requests: List[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.method == "GET":
            rows = self.payload if isinstance(self.payload, list) else self.payload.get("data", [])
            first = rows[0] if rows and isinstance(rows[0], dict) else {}
            fields = [{"Name": name, "DisplayName": name,
                       "Type": "Boolean" if isinstance(value, bool) else
                               "Number" if isinstance(value, (int, float)) else "String",
                       "Attributes": {"ShowOnGrid": True, "OntologyType": "TEXT"}}
                      for name, value in first.items() if name != "geometry"]
            return httpx.Response(200, json={
                "UniqueName": "transport", "Name": "Transport",
                "Description": "Moving entities", "Parameters": [], "Fields": fields,
            })
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


def posted_request(handler):
    return next(request for request in handler.requests if request.method == "POST")


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
    request = posted_request(handler)
    assert request.method == "POST"
    assert request.url.path == "/cube/v1/transport"
    assert request.headers["Authorization"] == "jwt"
    body = json.loads(request.content)
    assert body["eventTime"] == {"TimeBackUnit": "hour", "TimeBackValue": "1"}
    assert "Location" not in body["arriveTime.not"]


def test_pushes_boundary_as_wkt_location(tmp_path):
    provider, handler = make_provider(tmp_path, {"data": [record()]})
    boundary = box(34.7, 32.0, 34.9, 32.2)
    provider.fetch_features(layer(), geometry=boundary)
    body = json.loads(posted_request(handler).content)
    assert body["arriveTime.not"]["Location"] == boundary.wkt


def test_rechecks_boundary_when_cube_ignores_location(tmp_path):
    provider, _ = make_provider(tmp_path, [
        record("inside", "POINT (34.78 32.08)"),
        record("outside", "POINT (35.5 33.0)"),
    ])

    features = provider.fetch_features(
        layer(), geometry=box(34.7, 32.0, 34.9, 32.2))

    assert list(features["id"]) == ["inside"]


def test_schema_declares_event_time_and_point_geometry(tmp_path):
    provider, handler = make_provider(tmp_path, [record()])
    schema = provider.describe_schema(layer())
    assert schema.geometry_type == "Point"
    assert schema.temporal_field == "eventTime"
    assert {field.name for field in schema.fields} >= {"id", "callSign", "eventTime"}
    assert [request.method for request in handler.requests] == ["GET", "POST"]


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
    assert [request.method for request in handler.requests] == ["GET", "POST"]


def test_metadata_fields_and_parameters_are_authoritative(tmp_path):
    provider, handler = make_provider(tmp_path, [record()])
    original = handler.__call__

    def metadata_handler(request):
        if request.method == "GET":
            handler.requests.append(request)
            return httpx.Response(200, json={
                "Name": "Vehicle positions",
                "Description": "Last known positions",
                "Parameters": [{
                    "Name": "eventTime", "DisplayName": "Event time",
                    "Description": "Time window", "IsRequired": True,
                    "IsSingleValue": True, "Type": "DateTime", "Options": [],
                }],
                "Fields": [{
                    "Name": "netId", "DisplayName": "Network identity",
                    "Type": "String", "Attributes": {"ShowOnGrid": True},
                }],
            })
        return original(request)

    provider._transport = httpx.MockTransport(metadata_handler)
    schema = provider.describe_schema(layer())
    fields = {field.name: field for field in schema.fields}
    assert fields["netId"].description == "Network identity"
    assert schema.parameters[0].name == "eventTime"
    assert schema.parameters[0].required is True
    assert schema.source_name == "Vehicle positions"
    assert schema.source_description == "Last known positions"


def test_discovers_parameters_from_dedicated_endpoint(tmp_path):
    provider, handler = make_provider(tmp_path, [record()])

    def metadata_handler(request):
        handler.requests.append(request)
        if request.url.path.endswith("/parameters"):
            return httpx.Response(200, json=[{
                "Name": "eventTime", "DisplayName": "Event time",
                "IsRequired": True, "IsSingleValue": True,
                "OntologyType": "TIME", "Type": "DateTime", "Options": [],
            }])
        if request.method == "GET":
            return httpx.Response(200, json={"Name": "Transport", "Fields": []})
        return httpx.Response(200, json=[record()])

    provider._transport = httpx.MockTransport(metadata_handler)
    schema = provider.describe_schema(layer())
    assert [parameter.name for parameter in schema.parameters] == ["eventTime"]
    assert [request.url.path for request in handler.requests[:2]] == [
        "/cube/v1/transport", "/cube/v1/transport/parameters",
    ]


def test_rejects_unknown_required_parameter_instead_of_guessing(tmp_path):
    provider, handler = make_provider(tmp_path, [record()])

    def metadata_handler(request):
        handler.requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={
                "Parameters": [{
                    "Name": "forceType", "IsRequired": True,
                    "IsSingleValue": True, "Type": "String",
                    "Options": [{"Name": "Bus", "Value": "bus"}],
                }],
                "Fields": [],
            })
        return httpx.Response(200, json=[record()])

    provider._transport = httpx.MockTransport(metadata_handler)
    with pytest.raises(ProviderError, match="forceType.*no configured value"):
        provider.fetch_features(layer())


def test_match_and_not_parameter_names_map_to_request_operators(tmp_path):
    provider, handler = make_provider(tmp_path, [record()])

    def metadata_handler(request):
        handler.requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={
                "Parameters": [
                    {"Name": "eventTime.match", "IsRequired": True,
                     "IsSingleValue": True, "Type": "DateTime"},
                    {"Name": "eventTime.not", "IsRequired": True,
                     "IsSingleValue": True, "Type": "DateTime"},
                ],
                "Fields": [],
            })
        return httpx.Response(200, json=[record()])

    provider._transport = httpx.MockTransport(metadata_handler)
    boundary = box(34.7, 32.0, 34.9, 32.2)
    temporal_range = (
        "2024-11-26T00:00:00.000Z", "2024-11-26T23:59:59.000Z",
    )
    provider.fetch_features(
        layer(), geometry=boundary, temporal_range=temporal_range)
    body = json.loads(posted_request(handler).content)
    assert body == {
        "eventTime.match": {
            "From": temporal_range[0], "To": temporal_range[1],
        },
        "eventTime.not": {
            "TimeBackValue": "1", "TimeBackUnit": "hour",
            "Location": boundary.wkt,
        },
    }


def test_result_limit_adaptively_chunks_boundary_and_deduplicates(tmp_path):
    rows = [
        record("south-west", "POINT (34.71 32.01)"),
        record("south-east", "POINT (34.89 32.01)"),
        record("north-west", "POINT (34.71 32.19)"),
        record("north-east", "POINT (34.89 32.19)"),
    ]
    requests = []

    def handler(request):
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={
                "ResultsLimit": 2, "Parameters": [], "Fields": [],
            })
        location = json.loads(request.content)["arriveTime.not"]["Location"]
        boundary = wkt.loads(location)
        matching = [row for row in rows
                    if boundary.covers(wkt.loads(row["geometry"]))]
        return httpx.Response(200, json=matching[:2])

    store = RuntimeSettingsStore(Settings(
        _env_file=None,
        runtime_settings_file=str(tmp_path / "runtime-settings.json"),
        cubes_base_url="https://cubes.test",
        cubes_token="jwt",
    ))
    provider = CubesProvider(store, httpx.MockTransport(handler))

    features = provider.fetch_features(layer(), geometry=box(34.7, 32.0, 34.9, 32.2))

    assert set(features["id"]) == {
        "south-west", "south-east", "north-west", "north-east",
    }
    assert len([request for request in requests if request.method == "POST"]) == 5


def test_capped_result_without_boundary_fails_instead_of_truncating(tmp_path):
    provider, handler = make_provider(tmp_path, [record("one"), record("two")])

    def metadata_handler(request):
        handler.requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={
                "ResultsLimit": 2, "Parameters": [], "Fields": [],
            })
        return httpx.Response(200, json=[record("one"), record("two")])

    provider._transport = httpx.MockTransport(metadata_handler)

    with pytest.raises(ProviderError, match="result limit without a boundary"):
        provider.fetch_features(layer())


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
