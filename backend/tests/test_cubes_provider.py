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
from app.dal.providers.cubes import (
    CubesProvider,
    cubes_database_name,
    cubes_query_mode,
    cubes_resolved_parameters,
)


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
    configured = layer("cubes://db/transport?query_mode=match_not")
    assert cubes_database_name(configured) == "transport"
    assert cubes_query_mode(configured) == "match_not"


def test_explicit_match_not_mode_works_without_parameter_metadata(tmp_path):
    provider, handler = make_provider(tmp_path, [record()])
    boundary = box(34.7, 32.0, 34.9, 32.2)
    time_range = ("2024-11-26T00:00:00.000Z", "2024-11-26T23:59:59.000Z")

    provider.fetch_features(
        layer("cubes://db/transport?query_mode=match_not"),
        geometry=boundary, temporal_range=time_range,
    )
    body = json.loads(posted_request(handler).content)

    assert body["eventTime.match"] == {"From": time_range[0], "To": time_range[1]}
    assert body["eventTime.not"]["Location"] == boundary.wkt


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


def test_capped_result_without_boundary_returns_rows_as_is(tmp_path):
    """No boundary means there's nothing to chunk by, and Cubes has no
    pagination — a capped response is returned as-is rather than an error."""
    provider, handler = make_provider(tmp_path, [record("one"), record("two")])

    def metadata_handler(request):
        handler.requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={
                "ResultsLimit": 2, "Parameters": [], "Fields": [],
            })
        return httpx.Response(200, json=[record("one"), record("two")])

    provider._transport = httpx.MockTransport(metadata_handler)

    features = provider.fetch_features(layer())
    assert set(features["id"]) == {"one", "two"}


def test_capped_result_without_boundary_chunks_by_time_window(tmp_path):
    """No geometry but a real absolute {From, To} match window (match_not
    mode) — a capped response is recovered by bisecting the time window,
    same idea as spatial chunking but along the time axis."""
    rows = [
        record("morning", "POINT (34.78 32.08)"),
        record("evening", "POINT (34.79 32.09)"),
    ]
    requests = []
    full_from, full_to = "2024-11-26T00:00:00.000Z", "2024-11-26T23:59:59.000Z"

    def handler(request):
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={
                "ResultsLimit": 2, "Parameters": [], "Fields": [],
            })
        window = json.loads(request.content)["eventTime.match"]
        if window["From"] == full_from and window["To"] == full_to:
            return httpx.Response(200, json=rows)  # full range: capped at 2
        # First half of the day → "morning", second half → "evening".
        if window["To"] <= "2024-11-26T12:00:00.000Z":
            matching = [rows[0]]
        else:
            matching = [rows[1]]
        return httpx.Response(200, json=matching)

    store = RuntimeSettingsStore(Settings(
        _env_file=None,
        runtime_settings_file=str(tmp_path / "runtime-settings.json"),
        cubes_base_url="https://cubes.test",
        cubes_token="jwt",
    ))
    provider = CubesProvider(store, httpx.MockTransport(handler))

    features = provider.fetch_features(
        layer("cubes://db/transport?query_mode=match_not"),
        temporal_range=(full_from, full_to),
    )

    assert set(features["id"]) == {"morning", "evening"}
    assert len([r for r in requests if r.method == "POST"]) == 3  # 1 capped + 2 halves


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


def test_resolved_parameters_parsed_from_source_url():
    configured = layer(
        "cubes://db/transport?query_mode=match_not&param_TeamType=our_forces"
    )
    assert cubes_resolved_parameters(configured) == {"TeamType": "our_forces"}
    assert cubes_resolved_parameters(layer()) == {}


def test_dynamic_role_parameter_ignores_placeholder_options(tmp_path):
    provider, handler = make_provider(tmp_path, [record()])

    def metadata_handler(request):
        handler.requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={
                "Parameters": [{
                    "Name": "TeamType", "DisplayName": "סוג צוות",
                    "IsRequired": False, "IsSingleValue": True,
                    "Role": "dynamic", "Type": "String",
                    "Options": [{"Description": "", "Name": "", "Value": ""}],
                }],
                "Fields": [],
            })
        return httpx.Response(200, json=[record()])

    provider._transport = httpx.MockTransport(metadata_handler)
    schema = provider.describe_schema(layer())
    parameter = schema.parameters[0]
    assert parameter.is_dynamic is True
    assert parameter.options == []


def test_dynamic_parameter_required_without_resolved_value_fails(tmp_path):
    provider, handler = make_provider(tmp_path, [record()])

    def metadata_handler(request):
        handler.requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={
                "Parameters": [{
                    "Name": "TeamType", "IsRequired": True,
                    "IsSingleValue": True, "Role": "dynamic", "Type": "String",
                }],
                "Fields": [],
            })
        return httpx.Response(200, json=[record()])

    provider._transport = httpx.MockTransport(metadata_handler)
    with pytest.raises(ProviderError, match="TeamType.*no configured value"):
        provider.fetch_features(layer())


def test_dynamic_parameters_are_discovered_without_fetching_cube_rows(tmp_path):
    provider, handler = make_provider(tmp_path, [record()])

    def metadata_handler(request):
        handler.requests.append(request)
        assert request.method == "GET"
        return httpx.Response(200, json={
            "Parameters": [{
                "Name": "TeamType", "IsRequired": True,
                "Role": "dynamic", "Type": "String",
            }],
            "Fields": [],
        })

    provider._transport = httpx.MockTransport(metadata_handler)
    parameters = provider.list_dynamic_parameters(layer())

    assert [item.name for item in parameters] == ["TeamType"]
    assert parameters[0].resolved_value is None
    assert [request.method for request in handler.requests] == ["GET"]


def test_dynamic_suffix_parameter_is_discovered_without_role(tmp_path):
    provider, handler = make_provider(tmp_path, [record()])

    def metadata_handler(request):
        handler.requests.append(request)
        assert request.method == "GET"
        return httpx.Response(200, json={
            "Parameters": [{
                "Name": "fl:dynamic", "IsRequired": True, "Type": "String",
            }],
            "Fields": [],
        })

    provider._transport = httpx.MockTransport(metadata_handler)

    parameters = provider.list_dynamic_parameters(layer())

    assert [item.name for item in parameters] == ["fl:dynamic"]
    assert parameters[0].is_dynamic is True
    assert [request.method for request in handler.requests] == ["GET"]


def test_fl_dynamic_is_the_only_catalog_selector_when_present(tmp_path):
    provider, handler = make_provider(tmp_path, [record()])

    def metadata_handler(request):
        handler.requests.append(request)
        assert request.method == "GET"
        return httpx.Response(200, json={
            "Parameters": [
                {"Name": "fl:dynamic", "Type": "String"},
                {"Name": "environment", "Role": "dynamic", "Type": "String"},
                {"Name": "polygon", "Role": "dynamic", "Type": "String"},
            ],
            "Fields": [],
        })

    provider._transport = httpx.MockTransport(metadata_handler)

    parameters = provider.list_dynamic_parameters(layer())

    assert [item.name for item in parameters] == ["fl:dynamic"]


def test_dynamic_parameter_discovery_reads_resolved_source_value(tmp_path):
    provider, handler = make_provider(tmp_path, [record()])

    def metadata_handler(request):
        handler.requests.append(request)
        return httpx.Response(200, json={
            "Parameters": [{
                "Name": "TeamType", "IsRequired": True,
                "Role": "dynamic", "Type": "String",
            }],
            "Fields": [],
        })

    provider._transport = httpx.MockTransport(metadata_handler)
    configured = layer("cubes://db/transport?param_TeamType=our_forces")

    assert provider.list_dynamic_parameters(configured)[0].resolved_value == "our_forces"


def test_resolved_dynamic_parameter_value_is_injected_into_request_body(tmp_path):
    provider, handler = make_provider(tmp_path, [record()])

    def metadata_handler(request):
        handler.requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={
                "Parameters": [{
                    "Name": "TeamType", "IsRequired": True,
                    "IsSingleValue": True, "Role": "dynamic", "Type": "String",
                }],
                "Fields": [],
            })
        return httpx.Response(200, json=[record()])

    provider._transport = httpx.MockTransport(metadata_handler)
    provider.fetch_features(layer("cubes://db/transport?param_TeamType=our_forces"))
    body = json.loads(posted_request(handler).content)
    assert body["TeamType"] == "our_forces"


def test_dynamic_suffix_value_uses_exact_request_key(tmp_path):
    provider, handler = make_provider(tmp_path, [record()])

    def metadata_handler(request):
        handler.requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={
                "Parameters": [{
                    "Name": "fl:dynamic", "IsRequired": True, "Type": "String",
                }],
                "Fields": [],
            })
        return httpx.Response(200, json=[record()])

    provider._transport = httpx.MockTransport(metadata_handler)
    provider.fetch_features(layer(
        "cubes://db/rastaMorialand?param_fl%3Adynamic=612"
    ))

    body = json.loads(posted_request(handler).content)
    assert body["fl:dynamic"] == "612"


def test_fetch_autocomplete_options_posts_to_dedicated_route(tmp_path):
    provider, handler = make_provider(
        tmp_path, [{"Value": "system-a", "Name": "System A"},
                   {"Value": "system-b", "Name": "System B"}])

    def autocomplete_handler(request):
        handler.requests.append(request)
        return httpx.Response(200, json=[
            {"Value": "system-a", "Name": "System A"},
            {"Value": "system-b", "Name": "System B"},
        ])

    provider._transport = httpx.MockTransport(autocomplete_handler)
    options = provider.fetch_autocomplete_options(layer(), "sourceSystems")

    assert [(item.value, item.name) for item in options] == [
        ("system-a", "System A"), ("system-b", "System B"),
    ]
    request = handler.requests[0]
    assert request.method == "POST"
    assert request.url.path == "/cube/v1/transport/autocomplete/sourceSystems"
