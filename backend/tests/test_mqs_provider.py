import json
from typing import Callable, List, Optional

import httpx
import pytest

from app.bl.ports import LayerMeta
from app.common.config import Settings
from app.common.errors import ProviderError
from app.common.geo import WGS84
from app.common.runtime_settings import RuntimeSettingsStore
from app.dal.providers.mqs import (
    _MAX_FEATURES,
    _PAGE_SIZE,
    MqsProvider,
    mqs_layer_id,
)

BASE_URL = "https://mqs.test"


def make_store(tmp_path, mqs_base_url: Optional[str] = BASE_URL) -> RuntimeSettingsStore:
    env = Settings(
        _env_file=None,
        runtime_settings_file=str(tmp_path / "runtime-settings.json"),
        mqs_base_url=mqs_base_url,
    )
    return RuntimeSettingsStore(env)


def mqs_layer(layer_id: str = "42") -> LayerMeta:
    return LayerMeta(
        id="catalog-uuid", name="שכבת מוריה", provider="mqs",
        source_url=f"mqs://layer/{layer_id}",
    )


def feature(lng: float, lat: float, **properties) -> dict:
    return {
        "geometry": {"type": "Point", "coordinates": [lng, lat]},
        "properties": properties,
    }


class RecordingHandler:
    """MockTransport handler serving canned JSON per path, recording requests."""

    def __init__(self, responses: Callable[[httpx.Request], object]):
        self._responses = responses
        self.requests: List[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        result = self._responses(request)
        if isinstance(result, httpx.Response):
            return result
        return httpx.Response(200, json=result)


def make_provider(tmp_path, responses, mqs_base_url=BASE_URL):
    handler = RecordingHandler(responses)
    store = make_store(tmp_path, mqs_base_url=mqs_base_url)
    return MqsProvider(store, transport=httpx.MockTransport(handler)), handler


def test_layer_id_from_source_url():
    assert mqs_layer_id(mqs_layer("42")) == "42"
    bare = LayerMeta(id="x", name="n", provider="mqs", source_url="42")
    assert mqs_layer_id(bare) == "42"
    url = LayerMeta(
        id="x", name="n", provider="mqs",
        source_url="https://host/MoriaProject/42/",
    )
    assert mqs_layer_id(url) == "42"


def test_fetch_features_parses_geojson_features(tmp_path):
    provider, handler = make_provider(tmp_path, lambda request: {
        "features": [feature(34.78, 32.08, name="א"), feature(34.79, 32.09, name="ב")]
    })
    gdf = provider.fetch_features(mqs_layer())
    assert len(gdf) == 2
    assert str(gdf.crs) == WGS84
    assert list(gdf["name"]) == ["א", "ב"]
    request = handler.requests[0]
    assert request.url.path == "/MoriaProject/42/Entities"
    params = dict(request.url.params)
    assert params["geo_type"] == "GeoJSON"
    assert params["result_type"] == "data"
    assert params["from"] == "0"
    assert params["to"] == str(_PAGE_SIZE)


def test_fetch_features_flat_entities(tmp_path):
    provider, _ = make_provider(tmp_path, lambda request: {
        "data": [
            {"id": 1, "geom": {"type": "Point", "coordinates": [34.78, 32.08]},
             "name": "x"},
        ]
    })
    gdf = provider.fetch_features(mqs_layer())
    assert len(gdf) == 1
    assert gdf.iloc[0]["name"] == "x"
    assert gdf.iloc[0]["id"] == 1


def test_fetch_features_paginates(tmp_path):
    def responses(request):
        offset = int(dict(request.url.params)["from"])
        if offset == 0:
            return {"features": [feature(34.0, 32.0, i=i) for i in range(_PAGE_SIZE)]}
        return {"features": [feature(34.0, 32.0, i=offset)]}

    provider, handler = make_provider(tmp_path, responses)
    gdf = provider.fetch_features(mqs_layer())
    assert len(gdf) == _PAGE_SIZE + 1
    assert len(handler.requests) == 2
    assert dict(handler.requests[1].url.params)["from"] == str(_PAGE_SIZE)


def test_fetch_features_empty(tmp_path):
    provider, _ = make_provider(tmp_path, lambda request: {"features": []})
    gdf = provider.fetch_features(mqs_layer())
    assert len(gdf) == 0
    assert str(gdf.crs) == WGS84
    assert "geometry" in gdf.columns


def test_fetch_features_skips_bad_geometry(tmp_path):
    provider, _ = make_provider(tmp_path, lambda request: {
        "features": [
            feature(34.78, 32.08, name="good"),
            {"geometry": None, "properties": {"name": "bad"}},
            {"properties": {"name": "no-geometry-at-all"}},
        ]
    })
    gdf = provider.fetch_features(mqs_layer())
    assert list(gdf["name"]) == ["good"]


def test_fetch_features_hard_cap(tmp_path):
    full_page = {"features": [feature(34.0, 32.0) for _ in range(_PAGE_SIZE)]}
    provider, _ = make_provider(tmp_path, lambda request: full_page)
    with pytest.raises(ProviderError, match=str(_MAX_FEATURES)):
        provider.fetch_features(mqs_layer())


def test_fetch_features_http_error_wrapped(tmp_path):
    provider, _ = make_provider(
        tmp_path, lambda request: httpx.Response(500, text="boom")
    )
    with pytest.raises(ProviderError, match="MQS request failed"):
        provider.fetch_features(mqs_layer())


def test_fetch_features_invalid_json_wrapped(tmp_path):
    provider, _ = make_provider(
        tmp_path, lambda request: httpx.Response(200, text="<html>")
    )
    with pytest.raises(ProviderError, match="invalid JSON"):
        provider.fetch_features(mqs_layer())


def test_fetch_features_without_base_url(tmp_path):
    provider, handler = make_provider(tmp_path, lambda request: {}, mqs_base_url=None)
    with pytest.raises(ProviderError, match="not configured"):
        provider.fetch_features(mqs_layer())
    assert handler.requests == []


def test_fetch_features_accepts_now_kwarg(tmp_path, frozen_now):
    provider, _ = make_provider(tmp_path, lambda request: {"features": []})
    gdf = provider.fetch_features(mqs_layer(), now=frozen_now)
    assert len(gdf) == 0


def test_describe_schema_fields_and_samples(tmp_path):
    def responses(request):
        if request.url.path == "/MoriaProject/Layers/42":
            return {
                "geometryType": "Point",
                "fields": [
                    {"name": "status", "type": "string", "alias": "מצב"},
                    {"name": "size", "type": "double"},
                ],
            }
        if request.url.path == "/MoriaProject/ValueList/42":
            return {"status": ["פעיל", "סגור"], "size": [1, 2, 3]}
        raise AssertionError(f"unexpected path {request.url.path}")

    provider, _ = make_provider(tmp_path, responses)
    schema = provider.describe_schema(mqs_layer())
    assert schema.layer_id == "catalog-uuid"  # catalog id, not the MQS id
    assert schema.geometry_type == "Point"
    by_name = {f.name: f for f in schema.fields}
    assert by_name["status"].type == "string"
    assert by_name["status"].description == "מצב"
    assert by_name["status"].samples == ["פעיל", "סגור"]
    assert by_name["size"].type == "number"
    assert by_name["size"].samples == ["1", "2", "3"]


def test_describe_schema_valuelist_failure_is_soft(tmp_path):
    def responses(request):
        if request.url.path.startswith("/MoriaProject/ValueList/"):
            return httpx.Response(500)
        return {"geometryType": "Point", "fields": [{"name": "a", "type": "string"}]}

    provider, _ = make_provider(tmp_path, responses)
    schema = provider.describe_schema(mqs_layer())
    assert [f.name for f in schema.fields] == ["a"]
    assert schema.fields[0].samples == []


def test_describe_schema_unknown_shape(tmp_path):
    provider, _ = make_provider(tmp_path, lambda request: {})
    schema = provider.describe_schema(mqs_layer())
    assert schema.geometry_type == "unknown"
    assert schema.fields == []


def test_sample_field_values_from_value_list(tmp_path):
    def responses(request):
        if request.url.path == "/MoriaProject/ValueList/42":
            return [{"field": "status", "values": ["פעיל", "סגור", "בבנייה"]}]
        raise AssertionError(f"unexpected path {request.url.path}")

    provider, _ = make_provider(tmp_path, responses)
    values = provider.sample_field_values(mqs_layer(), "status")
    assert values == ["פעיל", "סגור", "בבנייה"]


def test_sample_field_values_entities_fallback(tmp_path):
    def responses(request):
        if request.url.path.startswith("/MoriaProject/ValueList/"):
            return {}
        return {"features": [
            feature(34.0, 32.0, status="פעיל"),
            feature(34.1, 32.1, status="סגור"),
            feature(34.2, 32.2, status="פעיל"),
        ]}

    provider, _ = make_provider(tmp_path, responses)
    values = provider.sample_field_values(mqs_layer(), "status")
    assert values == ["פעיל", "סגור"]  # distinct, order preserved


def test_sample_field_values_respects_limit(tmp_path):
    provider, _ = make_provider(tmp_path, lambda request: {
        "status": [f"v{i}" for i in range(50)]
    } if "ValueList" in request.url.path else {"features": []})
    values = provider.sample_field_values(mqs_layer(), "status", limit=5)
    assert values == ["v0", "v1", "v2", "v3", "v4"]


def test_list_remote_layers(tmp_path):
    provider, handler = make_provider(tmp_path, lambda request: {
        "layers": [{"id": 1, "name": "roads"}, {"id": 2, "name": "parks"}]
    })
    layers = provider.list_remote_layers()
    assert [layer["name"] for layer in layers] == ["roads", "parks"]
    assert handler.requests[0].url.path == "/MoriaProject/Layers"


def test_list_remote_layers_accepts_nested_pascal_case_envelope(tmp_path):
    provider, _ = make_provider(tmp_path, lambda request: {
        "Data": {"Items": [{"Id": 1, "Name": "roads"}]}
    })
    assert provider.list_remote_layers() == [{"Id": 1, "Name": "roads"}]


def test_list_remote_layers_rejects_unknown_200_response(tmp_path):
    provider, _ = make_provider(tmp_path, lambda request: {"success": True})
    with pytest.raises(ProviderError, match="unrecognized layer-list response"):
        provider.list_remote_layers()
