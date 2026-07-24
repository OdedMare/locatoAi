import json
from datetime import datetime, timezone
from typing import List, Optional

import httpx
import pytest
from shapely.geometry import box

from app.bl.catalog.models.layer_meta import LayerMeta
from app.common.config.settings import Settings
from app.common.errors.provider_error import ProviderError
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.providers.tyche.provider import TycheProvider


def layer(source_url="tyche://ourforces"):
    return LayerMeta(
        id="our-forces", name="כוחותינו", provider="tyche",
        source_url=source_url,
    )


def record(identifier="force-1", geometry="POINT (34.78 32.08)"):
    return {
        "eventTime": "2026-06-06 06:35:12.000",
        "arriveTime": "2026-06-06 06:35:18.000",
        "geometry": geometry,
        "callSign": "Alpha",
        "forceType": "vehicle",
        "unit": "unit-1",
        "netId": "net-1",
        "pstn": "123",
        "sourceType": "gps",
        "id": identifier,
        "trigger": "position",
        "locationType": "point",
    }


class RecordingHandler:
    def __init__(self, responses: List[dict]):
        self.responses = list(responses)
        self.requests: List[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, json=self.responses.pop(0))


def make_provider(
    tmp_path, responses, base_url: Optional[str] = "https://tyche.test",
    username="oded", token="Bearer secret",
):
    store = RuntimeSettingsStore(Settings(
        _env_file=None,
        runtime_settings_file=str(tmp_path / "runtime-settings.json"),
        tyche_base_url=base_url,
        tyche_username=username,
        tyche_token=token,
    ))
    handler = RecordingHandler(responses)
    provider = TycheProvider(store, httpx.MockTransport(handler))
    return provider, handler


def request_body(request: httpx.Request) -> dict:
    return json.loads(request.content)


def test_fetch_pushes_time_polygon_and_parses_wkt_geometry(tmp_path):
    provider, handler = make_provider(tmp_path, [{
        "results": [record()], "hasMoreResults": False, "pageTracker": "",
    }])
    boundary = box(34.7, 32.0, 34.9, 32.2)

    features = provider.fetch_features(
        layer(),
        now=datetime(2026, 6, 6, 8, 0, tzinfo=timezone.utc),
        geometry=boundary,
        temporal_range=(
            "2026-06-06T06:00:00.000Z", "2026-06-06T07:00:00.000Z"),
    )

    assert list(features["id"]) == ["force-1"]
    assert features.crs.to_string() == "EPSG:4326"
    assert features.iloc[0].geometry.x == 34.78
    request = handler.requests[0]
    assert request.url.path == "/coordinate/v1/ourforces"
    assert request.headers["Content-Type"] == "application/json"
    assert request.headers["username"] == "oded"
    assert request.headers["Authorization"] == "Bearer secret"
    body = request_body(request)
    assert body["eventTime"] == {"match": {
        "gte": "2026-06-06 06:00:00.000",
        "lte": "2026-06-06 07:00:00.000",
    }}
    assert body["location"] == {"match": boundary.wkt}
    assert body["size"] == 10000
    assert body["fetchPaging"] is True
    assert "noGeoQuery" not in body


def test_custom_layer_uses_its_route_and_field_mapping(tmp_path):
    provider, handler = make_provider(tmp_path, [{
        "results": [{
            "id": "alert-1",
            "observedAt": "2026-06-06 06:35:12.000",
            "geo": "POINT (34.78 32.08)",
            "severity": "high",
        }],
        "hasMoreResults": False,
    }])
    custom = layer(
        "tyche://alerts?geometry_field=geo"
        "&geo_query_field=area&time_field=observedAt"
    )
    boundary = box(34.7, 32.0, 34.9, 32.2)

    features = provider.fetch_features(custom, geometry=boundary)
    schema = provider.describe_schema(custom)

    assert list(features["id"]) == ["alert-1"]
    assert "geo" not in features.columns
    assert handler.requests[0].url.path == "/coordinate/v1/alerts"
    body = request_body(handler.requests[0])
    assert "eventTime" not in body
    assert body["area"] == {"match": boundary.wkt}
    assert "observedAt" in body
    assert schema.temporal_field == "observedAt"
    assert {field.name for field in schema.fields} == {
        "observedAt", "id", "severity",
    }


def test_default_event_window_is_one_hour_ending_at_now(tmp_path):
    provider, handler = make_provider(tmp_path, [{
        "results": [record()], "hasMoreResults": False,
    }])
    provider.fetch_features(
        layer(), now=datetime(2026, 6, 6, 7, 0, tzinfo=timezone.utc))

    assert request_body(handler.requests[0])["eventTime"] == {"match": {
        "gte": "2026-06-06 06:00:00.000",
        "lte": "2026-06-06 07:00:00.000",
    }}


def test_follows_page_tracker_deduplicates_and_honors_small_limit(tmp_path):
    provider, handler = make_provider(tmp_path, [
        {
            "results": [record("one"), record("two")],
            "pageTracker": "next-1", "hasMoreResults": True,
        },
        {
            "results": [record("two"), record("three")],
            "pageTracker": "next-2", "hasMoreResults": True,
        },
    ])

    features = provider.fetch_features(layer(), limit=3)

    assert list(features["id"]) == ["one", "two", "three"]
    assert len(handler.requests) == 2
    assert request_body(handler.requests[0])["size"] == 3
    second = request_body(handler.requests[1])
    assert second["pageTracker"] == "next-1"
    assert second["size"] == 1


def test_limit_stops_without_requesting_the_reported_next_page(tmp_path):
    provider, handler = make_provider(tmp_path, [{
        "results": [record("one")],
        "pageTracker": "next-1", "hasMoreResults": True,
    }])

    assert list(provider.fetch_features(layer(), limit=1)["id"]) == ["one"]
    assert len(handler.requests) == 1
    assert request_body(handler.requests[0])["size"] == 1


def test_geometry_accepts_geojson_object_and_encoded_geojson(tmp_path):
    geojson = {"type": "Point", "coordinates": [34.78, 32.08]}
    provider, _ = make_provider(tmp_path, [{
        "results": [
            record("object", geojson),
            record("string", json.dumps(geojson)),
        ],
        "hasMoreResults": False,
    }])

    features = provider.fetch_features(layer())

    assert list(features["id"]) == ["object", "string"]
    assert list(features.geometry.x) == [34.78, 34.78]


def test_locally_rechecks_geometry_and_skips_invalid_values(tmp_path):
    provider, _ = make_provider(tmp_path, [{
        "results": [
            record("inside", "POINT (34.78 32.08)"),
            record("outside", "POINT (35.5 33.0)"),
            record("bad", "not-geometry"),
        ],
        "hasMoreResults": False,
    }])

    features = provider.fetch_features(
        layer(), geometry=box(34.7, 32.0, 34.9, 32.2))

    assert list(features["id"]) == ["inside"]


def test_schema_is_documented_and_enriched_with_sample_fields(tmp_path):
    row = record()
    row["quality"] = 95
    provider, _ = make_provider(tmp_path, [{
        "results": [row], "hasMoreResults": False,
    }])
    provider.fetch_features(layer())

    schema = provider.describe_schema(layer())
    fields = {field.name: field for field in schema.fields}

    assert schema.geometry_type == "Geometry"
    assert schema.temporal_field == "eventTime"
    assert fields["callSign"].samples == ["Alpha"]
    assert fields["quality"].samples == ["95"]


def test_sample_field_values_fetches_a_bounded_sample(tmp_path):
    provider, handler = make_provider(tmp_path, [{
        "results": [record("one"), record("two"), record("one")],
        "hasMoreResults": False,
    }])

    assert provider.sample_field_values(layer(), "id") == ["one", "two"]
    assert request_body(handler.requests[0])["size"] == 100


def test_paging_requires_a_new_tracker(tmp_path):
    provider, _ = make_provider(tmp_path, [{
        "results": [record()], "hasMoreResults": True,
    }])
    with pytest.raises(ProviderError, match="without a pageTracker"):
        provider.fetch_features(layer())


def test_rejects_invalid_response_and_missing_configuration(tmp_path):
    provider, _ = make_provider(tmp_path, [{"results": "not-a-list"}])
    with pytest.raises(ProviderError, match="results array"):
        provider.fetch_features(layer())

    provider, _ = make_provider(tmp_path, [], base_url=None)
    with pytest.raises(ProviderError, match="base URL"):
        provider.fetch_features(layer())

    provider, _ = make_provider(tmp_path, [], username="")
    with pytest.raises(ProviderError, match="username"):
        provider.fetch_features(layer())

    provider, _ = make_provider(tmp_path, [], token="")
    with pytest.raises(ProviderError, match="token"):
        provider.fetch_features(layer())


def test_rejects_invalid_catalog_source(tmp_path):
    provider, _ = make_provider(tmp_path, [])

    with pytest.raises(ProviderError, match="tyche:// scheme"):
        provider.fetch_features(layer("https://tyche.test/alerts"))
