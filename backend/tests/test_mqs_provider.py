import json
from typing import Callable, List, Optional

import httpx
import pytest
from shapely.geometry import Polygon, box

from app.bl.catalog.models.layer_meta import LayerMeta
from app.bl.catalog.mqs_sync.browse_mqs_layers import browse_mqs_layers
from app.common.config.settings import Settings
from app.common.errors.provider_error import ProviderError
from app.common.utils.geo_utils import WGS84
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.providers.mqs.provider import (
    _MAX_FEATURES_PER_LAYER,
    _PAGE_SIZE,
    MqsProvider,
    mqs_layer_id,
)

BASE_URL = "https://mqs.test"


def make_store(
    tmp_path,
    mqs_base_url: Optional[str] = BASE_URL,
    mqs_user_id: Optional[str] = None,
) -> RuntimeSettingsStore:
    env = Settings(
        _env_file=None,
        runtime_settings_file=str(tmp_path / "runtime-settings.json"),
        mqs_base_url=mqs_base_url,
        mqs_user_id=mqs_user_id,
    )
    return RuntimeSettingsStore(env)


def mqs_layer(layer_id: str = "42") -> LayerMeta:
    return LayerMeta(
        id="catalog-uuid", name="שכבת מוריה", provider="mqs",
        source_url=f"mqs://layer/{layer_id}",
    )


def entity(
    entity_id: str = "{GUID}",
    layer_id: str = "42",
    wkt_value: str = "POINT (34.78 32.08 0)",
    triangle: str = "0",
    clearence_level: str = "0",
    source_id: int = 700009,
    date: str = "13/07/2026 08:30:00",
    area: float = 0.00000001,
    perimeter: float = 0.0005,
    property_list=None,
) -> dict:
    """One entity per the real MoriaProject API doc's fixed shape."""
    result = {
        "exclusive_id": {
            "data_store_name": "MoriaProject", "layer_id": layer_id,
            "entity_id": entity_id, "history_id": 1,
        },
        "classification": {
            "triangle": triangle, "clearence_level": clearence_level,
            "source_id": source_id,
        },
        "date": date,
        "link": f"https://mqs.test/MoriaProject/{layer_id}/Entities/{entity_id}",
        "geo": {"wkt": wkt_value, "area": area, "perimeter": perimeter},
    }
    if property_list is not None:
        result["property_list"] = property_list
    return result


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


def make_provider(tmp_path, responses, mqs_base_url=BASE_URL, mqs_user_id=None):
    handler = RecordingHandler(responses)
    store = make_store(tmp_path, mqs_base_url=mqs_base_url, mqs_user_id=mqs_user_id)
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


def test_layer_id_from_pasted_entities_link():
    """A full layer_entities_link as source_url must yield the id, not
    the trailing 'Entities' endpoint word."""
    pasted = LayerMeta(
        id="x", name="n", provider="mqs",
        source_url="https://host/MoriaProject/110/Entities",
    )
    assert mqs_layer_id(pasted) == "110"
    bad = LayerMeta(id="x", name="n", provider="mqs", source_url="/Entities/")
    with pytest.raises(ProviderError, match="no MQS layer id"):
        mqs_layer_id(bad)


def test_fetch_features_parses_entities_list_wrapper(tmp_path):
    """The doc's paginated shape: {"entities_list": [...], "next_page": null}."""
    provider, handler = make_provider(tmp_path, lambda request: {
        "next_page": None,
        "total_entities": 2,
        "entities_list": [
            entity("{G1}", wkt_value="POINT (34.78 32.08 0)"),
            entity("{G2}", wkt_value="POINT (34.79 32.09 0)"),
        ],
    })
    gdf = provider.fetch_features(mqs_layer())
    assert len(gdf) == 2
    assert str(gdf.crs) == WGS84
    assert list(gdf["id"]) == ["{G1}", "{G2}"]
    request = handler.requests[0]
    assert request.method == "GET"
    assert request.url.path == "/MoriaProject/42/Entities"
    assert dict(request.url.params) == {"from": "0", "to": str(_PAGE_SIZE)}
    assert request.headers["Accept"] == "application/json"


def test_fetch_features_parses_bare_array_response(tmp_path):
    """The doc's first (non-paginated) section shows a bare JSON array —
    still accepted."""
    provider, _ = make_provider(tmp_path, lambda request: [entity("{G1}")])
    gdf = provider.fetch_features(mqs_layer())
    assert len(gdf) == 1


def test_fetch_features_extracts_fixed_fields(tmp_path):
    provider, _ = make_provider(tmp_path, lambda request: [entity(
        "{G1}", triangle="678588", clearence_level="2", source_id=42,
        date="15/06/2025 20:35:33", area=1.5357398e-8, perimeter=0.0005615732822034,
    )])
    gdf = provider.fetch_features(mqs_layer())
    row = gdf.iloc[0]
    assert row["id"] == "{G1}"
    assert row["triangle"] == "678588"
    assert row["clearence_level"] == "2"  # service spelling preserved
    assert row["source_id"] == 42
    assert row["date"] == "15/06/2025 20:35:33"
    assert row["area"] == 1.5357398e-8
    assert row["perimeter"] == 0.0005615732822034
    assert "link" in gdf.columns
    assert row.geometry.geom_type == "Polygon" or row.geometry.geom_type == "Point"


def test_fetch_features_enriches_business_fields_from_entity_detail(tmp_path):
    listed = entity("{G1}")
    detailed = entity("{G1}", property_list={
        "שם": "בית ספר אלונים",
        "מהות": "חינוך",
        "סוג": "יסודי",
    })

    def responses(request):
        if request.url.path.endswith("/EntityInfo/{G1}"):
            return detailed
        return {"next_page": None, "entities_list": [listed]}

    provider, handler = make_provider(tmp_path, responses)
    gdf = provider.fetch_features(mqs_layer())
    assert gdf.iloc[0]["שם"] == "בית ספר אלונים"
    assert gdf.iloc[0]["מהות"] == "חינוך"
    assert gdf.iloc[0]["סוג"] == "יסודי"
    assert any("/EntityInfo/%7BG1%7D" in request.url.raw_path.decode()
               for request in handler.requests)


def test_entity_detail_calls_entityinfo_not_entities(tmp_path):
    listed = entity("{G1}")
    detailed = entity("{G1}", property_list={"שם": "פארק הירקון"})

    def responses(request):
        if request.url.path.endswith("/Entities/{G1}"):
            raise AssertionError("detail fetch must not hit /Entities/{entity_id}")
        if request.url.path.endswith("/EntityInfo/{G1}"):
            return detailed
        return {"next_page": None, "entities_list": [listed]}

    provider, handler = make_provider(tmp_path, responses)
    provider.fetch_features(mqs_layer())
    assert any("/EntityInfo/%7BG1%7D" in request.url.raw_path.decode()
               for request in handler.requests)


def test_entity_detail_url_encodes_reserved_entity_id_characters(tmp_path):
    entity_id = "source/folder?id=1"
    listed = entity(entity_id)
    detailed = entity(entity_id, property_list={"name": "encoded"})

    def responses(request):
        if "/EntityInfo/" in request.url.path:
            return detailed
        return {"next_page": None, "entities_list": [listed]}

    provider, handler = make_provider(tmp_path, responses)

    features = provider.fetch_features(mqs_layer())

    assert features.iloc[0]["name"] == "encoded"
    detail_request = next(
        request for request in handler.requests
        if "/EntityInfo/" in request.url.path
    )
    assert detail_request.url.raw_path.decode().endswith(
        "/EntityInfo/source%2Ffolder%3Fid%3D1"
    )


def test_entityinfo_502_falls_back_to_list_entity(tmp_path):
    listed = entity("{G1}")

    def responses(request):
        if request.url.path.endswith("/EntityInfo/{G1}"):
            return httpx.Response(502, json={"error": "upstream unavailable"})
        return {"next_page": None, "entities_list": [listed]}

    provider, handler = make_provider(tmp_path, responses)

    gdf = provider.fetch_features(mqs_layer())

    assert len(gdf) == 1
    assert gdf.iloc[0]["id"] == "{G1}"
    assert gdf.iloc[0].geometry is not None
    assert any("/EntityInfo/%7BG1%7D" in request.url.raw_path.decode()
               for request in handler.requests)


def test_fetch_features_accepts_property_list_name_value_array(tmp_path):
    provider, _ = make_provider(tmp_path, lambda request: [entity(
        "{G1}", property_list=[
            {"property_name": "שם", "property_value": "כיכר המדינה"},
            {"name": "סוג", "value": "כיכר"},
        ],
    )])
    row = provider.fetch_features(mqs_layer()).iloc[0]
    assert row["שם"] == "כיכר המדינה"
    assert row["סוג"] == "כיכר"


def test_property_list_accepts_camel_case_and_json_string(tmp_path):
    properties = json.dumps([
        {"propertyName": "שם", "propertyValue": "בית הכנסת הגדול"},
        {"FieldName": "מהות", "FieldValue": "בית כנסת"},
    ], ensure_ascii=False)
    provider, _ = make_provider(tmp_path, lambda request: [entity(
        "{G1}", property_list=properties,
    )])

    row = provider.fetch_features(mqs_layer()).iloc[0]

    assert row["שם"] == "בית הכנסת הגדול"
    assert row["מהות"] == "בית כנסת"


def test_property_list_accepts_nested_properties_wrapper(tmp_path):
    provider, _ = make_provider(tmp_path, lambda request: [entity(
        "{G1}", property_list={"Properties": [
            {"PropertyName": "סוג", "PropertyValue": "ציבורי"},
        ]},
    )])

    row = provider.fetch_features(mqs_layer()).iloc[0]

    assert row["סוג"] == "ציבורי"


def test_describe_schema_and_sample_values_use_property_list(tmp_path):
    detailed = entity("G1", property_list={"שם": "גן העיר", "סוג": "ציבורי"})

    def responses(request):
        if request.url.path.endswith("/EntityInfo/G1"):
            return detailed
        return {"next_page": None, "entities_list": [entity("G1")]}

    provider, _ = make_provider(tmp_path, responses)
    schema = provider.describe_schema(mqs_layer())
    fields = {field.name: field for field in schema.fields}
    assert fields["שם"].samples == ["גן העיר"]
    assert fields["סוג"].samples == ["ציבורי"]
    assert provider.sample_field_values(mqs_layer(), "שם") == ["גן העיר"]


def test_fetch_features_follows_next_page(tmp_path):
    page_1 = {
        "next_page": "https://mqs.test/MQS/MoriaProject/42/Entities?from=2&to=4",
        "total_entities": 3,
        "entities_list": [entity("{G1}"), entity("{G2}")],
    }
    page_2 = {
        "next_page": None,
        "total_entities": 3,
        "entities_list": [entity("{G3}")],
    }

    def responses(request):
        params = dict(request.url.params)
        if params.get("from") == "2":
            return page_2
        return page_1

    provider, handler = make_provider(tmp_path, responses)
    gdf = provider.fetch_features(mqs_layer())
    assert len(gdf) == 3
    page_requests = [
        request for request in handler.requests
        if request.url.path.endswith("/Entities")
    ]
    assert len(page_requests) == 2
    assert dict(page_requests[1].url.params) == {"from": "2", "to": "4"}


def test_fetch_features_empty(tmp_path):
    provider, _ = make_provider(
        tmp_path, lambda request: {"next_page": None, "entities_list": []}
    )
    gdf = provider.fetch_features(mqs_layer())
    assert len(gdf) == 0
    assert str(gdf.crs) == WGS84
    assert "geometry" in gdf.columns


def test_fetch_features_skips_bad_geometry(tmp_path):
    def responses(request):
        good = entity("{G1}")
        bad = entity("{G2}")
        bad["geo"] = {"wkt": "not-wkt", "area": 0, "perimeter": 0}
        no_geo = entity("{G3}")
        del no_geo["geo"]
        return {"next_page": None, "entities_list": [good, bad, no_geo]}

    provider, _ = make_provider(tmp_path, responses)
    gdf = provider.fetch_features(mqs_layer())
    assert list(gdf["id"]) == ["{G1}"]


def test_fetch_features_per_layer_hard_cap(tmp_path):
    """An unbounded (no geometry) layer load is capped at
    _MAX_FEATURES_PER_LAYER (10,000), stricter than the whole-request
    _MAX_FEATURES (50,000) ceiling."""
    huge_page = {
        "next_page": None,
        "entities_list": [entity(str(i)) for i in range(_MAX_FEATURES_PER_LAYER + 1)],
    }
    provider, _ = make_provider(tmp_path, lambda request: huge_page)
    with pytest.raises(ProviderError, match=str(_MAX_FEATURES_PER_LAYER)):
        provider.fetch_features(mqs_layer())


def test_fetch_features_within_geometry_hard_cap(tmp_path):
    """A bounded (geometry-split) layer load is also capped at the
    per-layer 10,000 limit, not the looser whole-request 50,000 ceiling.
    total_entities is reported as exactly _MAX_FEATURES_PER_LAYER (at, not
    over, _GEO_CHUNK_TARGET) so the region never looks overloaded and no
    quadrant split happens; a full first page plus one extra entity on
    page 2 is what actually trips the cap, keeping the fixture cheap."""
    boundary = box(34.78, 32.08, 34.80, 32.10)

    def responses(request):
        params = dict(request.url.params)
        if params.get("from") == "0":
            return {
                "next_page": "https://mqs.test/MoriaProject/42/Entities?from=10000&to=20000",
                "total_entities": _MAX_FEATURES_PER_LAYER,
                "entities_list": [entity(str(i)) for i in range(_MAX_FEATURES_PER_LAYER)],
            }
        return {
            "next_page": None,
            "total_entities": _MAX_FEATURES_PER_LAYER,
            "entities_list": [entity("overflow")],
        }

    provider, _ = make_provider(tmp_path, responses)
    with pytest.raises(ProviderError, match=str(_MAX_FEATURES_PER_LAYER)):
        provider.fetch_features(mqs_layer(), geometry=boundary)


def test_fetch_features_http_error_wrapped(tmp_path):
    provider, _ = make_provider(
        tmp_path, lambda request: httpx.Response(500, text="boom")
    )
    with pytest.raises(ProviderError, match="MQS request failed"):
        provider.fetch_features(mqs_layer())


def test_mqs_500_without_user_id_has_actionable_error(tmp_path):
    provider, _ = make_provider(
        tmp_path,
        lambda request: httpx.Response(500, json={"error": "missing identity"}),
    )

    with pytest.raises(ProviderError) as raised:
        provider.fetch_features(mqs_layer())

    message = str(raised.value)
    assert "500 Internal Server Error" in message
    assert "missing identity" in message
    assert "User_ID is not configured" in message


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
    provider, _ = make_provider(
        tmp_path, lambda request: {"next_page": None, "entities_list": []}
    )
    gdf = provider.fetch_features(mqs_layer(), now=frozen_now)
    assert len(gdf) == 0


def test_fetch_features_rejects_non_wgs84_coordinates(tmp_path):
    """A live instance serving a projected CRS (e.g. ITM/EPSG:2039) instead
    of WGS84 lon/lat must fail loudly, not silently mislabel the geometry —
    regression guard for the CRS-confusion class of geography bugs."""
    itm_like_entity = entity("{G1}", wkt_value="POINT (178000 664000 0)")
    provider, _ = make_provider(
        tmp_path, lambda request: {"next_page": None, "entities_list": [itm_like_entity]}
    )
    with pytest.raises(ProviderError, match="outside WGS84"):
        provider.fetch_features(mqs_layer())


def test_fetch_features_unrecognized_shape_raises(tmp_path):
    provider, _ = make_provider(tmp_path, lambda request: {"success": True})
    with pytest.raises(ProviderError, match="unrecognized Entities response"):
        provider.fetch_features(mqs_layer())


def test_fetch_features_without_geometry_stays_get(tmp_path):
    """No geometry hint → unchanged GET behavior (no regression)."""
    provider, handler = make_provider(
        tmp_path, lambda request: {"next_page": None, "entities_list": [entity("{G1}")]}
    )
    provider.fetch_features(mqs_layer())
    assert handler.requests[0].method == "GET"


def test_fetch_features_with_bbox_geometry_posts_geo_bounding_box(tmp_path):
    """An axis-aligned rectangle (the viewport case) becomes a POST with
    geo_bounding_box, not GET — spatial pushdown per the filter doc."""
    provider, handler = make_provider(
        tmp_path, lambda request: {"next_page": None, "entities_list": [entity("{G1}")]}
    )
    viewport = box(34.7, 32.0, 34.9, 32.2)  # minx, miny, maxx, maxy
    provider.fetch_features(mqs_layer(), geometry=viewport)

    request = handler.requests[0]
    assert request.method == "POST"
    assert request.url.path == "/MoriaProject/42/Entities"
    body = json.loads(request.content)
    bbox = body["filter"]["complex_operators"]["geo_bounding_box"]["geo"]["values"][0]
    assert bbox["location_top_left"] == {"lat": 32.2, "lon": 34.7}
    assert bbox["location_bottom_right"] == {"lat": 32.0, "lon": 34.9}
    # pagination params still applied on the POST path
    assert dict(request.url.params) == {"from": "0", "to": str(_PAGE_SIZE)}


def test_fetch_features_with_polygon_geometry_posts_geo_polygon(tmp_path):
    """A non-rectangular shape (a drawn polygon) becomes geo_polygon WKT."""
    provider, handler = make_provider(
        tmp_path, lambda request: {"next_page": None, "entities_list": []}
    )
    triangle = Polygon([(34.7, 32.0), (34.9, 32.0), (34.8, 32.3)])
    provider.fetch_features(mqs_layer(), geometry=triangle)

    request = handler.requests[0]
    assert request.method == "POST"
    body = json.loads(request.content)
    geo_polygon = body["filter"]["complex_operators"]["geo_polygon"]["geo"]
    assert geo_polygon["type"] == "IN"
    assert geo_polygon["values"] == [triangle.wkt]


def test_fetch_features_with_attribute_filters_posts_simple_operators_match(tmp_path):
    provider, handler = make_provider(
        tmp_path, lambda request: {"next_page": None, "entities_list": [entity("{G1}")]}
    )
    provider.fetch_features(mqs_layer(), attribute_filters=[("סוג", "בית ספר")])

    request = handler.requests[0]
    assert request.method == "POST"
    body = json.loads(request.content)
    assert body["filter"]["simple_operators"]["match"]["סוג"] == {
        "type": "IN", "values": ["בית ספר"]
    }
    assert "complex_operators" not in body["filter"]


def test_fetch_features_with_attribute_filters_and_geometry_merges_both(tmp_path):
    provider, handler = make_provider(
        tmp_path, lambda request: {"next_page": None, "entities_list": [entity("{G1}")]}
    )
    viewport = box(34.7, 32.0, 34.9, 32.2)
    provider.fetch_features(
        mqs_layer(), geometry=viewport, attribute_filters=[("סוג", "בית ספר")]
    )

    request = handler.requests[0]
    assert request.method == "POST"
    body = json.loads(request.content)
    assert "geo_bounding_box" in body["filter"]["complex_operators"]
    assert body["filter"]["simple_operators"]["match"]["סוג"] == {
        "type": "IN", "values": ["בית ספר"]
    }


def test_fetch_features_with_multiple_attribute_filters(tmp_path):
    provider, handler = make_provider(
        tmp_path, lambda request: {"next_page": None, "entities_list": [entity("{G1}")]}
    )
    provider.fetch_features(
        mqs_layer(),
        attribute_filters=[("סוג", "בית ספר"), ("מהות", "חינוך")],
    )

    body = json.loads(handler.requests[0].content)
    match = body["filter"]["simple_operators"]["match"]
    assert match["סוג"] == {"type": "IN", "values": ["בית ספר"]}
    assert match["מהות"] == {"type": "IN", "values": ["חינוך"]}


def test_fetch_features_attribute_filters_alone_without_geometry_still_posts(tmp_path):
    """Regression: attribute_filters alone (no geometry) must still trigger
    POST, not GET — the GET/POST decision no longer depends on geometry only."""
    provider, handler = make_provider(
        tmp_path, lambda request: {"next_page": None, "entities_list": [entity("{G1}")]}
    )
    provider.fetch_features(mqs_layer(), attribute_filters=[("סוג", "בית ספר")])

    assert handler.requests[0].method == "POST"


def test_fetch_features_without_attribute_filters_stays_get(tmp_path):
    provider, handler = make_provider(
        tmp_path, lambda request: {"next_page": None, "entities_list": [entity("{G1}")]}
    )
    provider.fetch_features(mqs_layer())

    assert handler.requests[0].method == "GET"


def test_dense_small_geometry_is_split_and_cross_tile_entities_are_deduplicated(
    tmp_path,
):
    """Density, not physical size, triggers adaptive geographic chunks."""
    boundary = box(34.78, 32.08, 34.80, 32.10)

    def responses(request):
        body = json.loads(request.content)
        value = body["filter"]["complex_operators"]["geo_bounding_box"]["geo"]
        locations = value["values"][0]
        top_left = locations["location_top_left"]
        bottom_right = locations["location_bottom_right"]
        is_root = (
            top_left == {"lat": 32.1, "lon": 34.78}
            and bottom_right == {"lat": 32.08, "lon": 34.8}
        )
        return {
            "next_page": None,
            "total_entities": 40000 if is_root else 5000,
            # A polygon crossing tile boundaries may be returned by several
            # chunks. One stable entity id must still produce one result.
            "entities_list": [entity(
                "same", wkt_value="POINT (34.79 32.09)", property_list={}
            )],
        }

    provider, handler = make_provider(tmp_path, responses)

    result = provider.fetch_features(mqs_layer(), geometry=boundary)

    assert list(result["id"]) == ["same"]
    requests = [request for request in handler.requests
                if request.url.path.endswith("/Entities")]
    assert len(requests) == 5  # one density probe + four quadrants


def test_geo_chunking_stops_when_mqs_does_not_narrow_tiles(tmp_path):
    """An ignored geo filter must not create an exponential request storm."""
    provider, handler = make_provider(tmp_path, lambda request: {
        "next_page": None,
        "total_entities": 40000,
        "entities_list": [entity(
            "same", wkt_value="POINT (34.79 32.09)", property_list={}
        )],
    })

    result = provider.fetch_features(
        mqs_layer(), geometry=box(34.78, 32.08, 34.80, 32.10)
    )

    assert list(result["id"]) == ["same"]
    assert len(handler.requests) == 5


def test_geometry_filter_is_rechecked_when_mqs_ignores_it(tmp_path):
    """Only polygon matches may enter GeoPandas, even if MQS returns extras."""
    provider, _ = make_provider(tmp_path, lambda request: {
        "next_page": None,
        "entities_list": [
            entity("inside", wkt_value="POINT (34.78 32.08)", property_list={}),
            entity("outside", wkt_value="POINT (35.5 33.0)", property_list={}),
        ],
    })

    result = provider.fetch_features(
        mqs_layer(), geometry=box(34.7, 32.0, 34.9, 32.2))

    assert list(result["id"]) == ["inside"]


def test_fetch_features_with_geometry_follows_pagination(tmp_path):
    """Spatial pushdown and pagination compose — next_page still followed
    on the POST path."""
    page_1 = {
        "next_page": "https://mqs.test/MQS/MoriaProject/42/Entities?from=1&to=2",
        "entities_list": [entity("{G1}")],
    }
    page_2 = {"next_page": None, "entities_list": [entity("{G2}")]}

    def responses(request):
        params = dict(request.url.params)
        return page_2 if params.get("from") == "1" else page_1

    provider, handler = make_provider(tmp_path, responses)
    gdf = provider.fetch_features(mqs_layer(), geometry=box(34.0, 32.0, 35.0, 33.0))
    assert len(gdf) == 2
    page_requests = [
        request for request in handler.requests
        if request.url.path.endswith("/Entities")
    ]
    assert all(request.method == "POST" for request in page_requests)
    assert dict(page_requests[1].url.params) == {"from": "1", "to": "2"}


def test_fetch_features_with_limit_caps_page_size(tmp_path):
    """A metadata-sampling caller passing limit=100 must request a small
    first page, not the full _PAGE_SIZE — this is the whole point of the
    limit hint (avoid a full paginated fetch just to sample a layer)."""
    provider, handler = make_provider(tmp_path, lambda request: {
        "next_page": None, "entities_list": [entity(str(i)) for i in range(5)],
    })
    provider.fetch_features(mqs_layer(), limit=100)
    assert dict(handler.requests[0].url.params) == {"from": "0", "to": "100"}


def test_fetch_features_with_limit_stops_without_following_next_page(tmp_path):
    """Once `limit` entities have been yielded, no further page should be
    requested even if next_page is present."""
    def responses(request):
        return {
            "next_page": "https://mqs.test/MQS/MoriaProject/42/Entities?from=3&to=6",
            "entities_list": [entity(str(i)) for i in range(3)],
        }

    provider, handler = make_provider(tmp_path, responses)
    gdf = provider.fetch_features(mqs_layer(), limit=2)
    assert len(gdf) == 2
    page_requests = [
        request for request in handler.requests
        if request.url.path.endswith("/Entities")
    ]
    assert len(page_requests) == 1


def test_metadata_sample_reuses_entities_for_schema_and_stops_after_ten(tmp_path):
    listed = [entity(str(index)) for index in range(30)]

    def responses(request):
        if "/EntityInfo/" in request.url.path:
            entity_id = request.url.path.rsplit("/", 1)[-1]
            return entity(entity_id, property_list={
                "name": f"place-{entity_id}", "kind": "business",
            })
        return {"next_page": None, "entities_list": listed}

    provider, handler = make_provider(tmp_path, responses)

    features, schema = provider.sample_for_metadata(mqs_layer(), limit=100)

    assert len(features) == 10
    assert {field.name for field in schema.fields} >= {"name", "kind"}
    entity_requests = [
        request for request in handler.requests
        if request.url.path.endswith("/Entities")
    ]
    detail_requests = [
        request for request in handler.requests
        if "/EntityInfo/" in request.url.path
    ]
    assert len(entity_requests) == 1
    assert len(detail_requests) == 10
    assert dict(entity_requests[0].url.params) == {"from": "0", "to": "10"}


def test_user_id_header_sent_when_configured(tmp_path):
    """The doc marks User_ID as a required header — it must reach every
    MQS request when the mqs_user_id setting is set."""
    provider, handler = make_provider(
        tmp_path, lambda request: {"next_page": None, "entities_list": []},
        mqs_user_id="tt/T",
    )
    provider.fetch_features(mqs_layer())
    assert handler.requests[0].headers["User_ID"] == "tt/T"


def test_user_id_header_omitted_when_unset(tmp_path):
    provider, handler = make_provider(
        tmp_path, lambda request: {"next_page": None, "entities_list": []}
    )
    provider.fetch_features(mqs_layer())
    assert "User_ID" not in handler.requests[0].headers


def test_describe_schema_returns_fixed_fields(tmp_path):
    """Fixed transport fields remain present when a layer has no entities."""
    provider, handler = make_provider(
        tmp_path, lambda request: {"next_page": None, "entities_list": []}
    )
    schema = provider.describe_schema(mqs_layer())
    assert schema.layer_id == "catalog-uuid"
    assert schema.geometry_type == "Polygon"
    names = {f.name for f in schema.fields}
    assert names == {"triangle", "clearence_level", "source_id", "date", "area", "perimeter"}
    assert schema.temporal_field == "date"
    assert len(handler.requests) == 1


def test_describe_schema_temporal_field_tag_override(tmp_path):
    provider, _ = make_provider(
        tmp_path, lambda request: {"next_page": None, "entities_list": []}
    )
    layer = mqs_layer().model_copy(update={"tags": ["temporal_field:custom_date"]})
    schema = provider.describe_schema(layer)
    assert schema.temporal_field == "custom_date"


def test_describe_schema_no_temporal_field_tag_opts_out(tmp_path):
    provider, _ = make_provider(
        tmp_path, lambda request: {"next_page": None, "entities_list": []}
    )
    layer = mqs_layer().model_copy(update={"tags": ["no_temporal_field"]})
    schema = provider.describe_schema(layer)
    assert schema.temporal_field is None


def test_sample_field_values_from_fixed_field(tmp_path):
    provider, _ = make_provider(tmp_path, lambda request: {
        "next_page": None,
        "entities_list": [
            entity("{G1}", triangle="0"),
            entity("{G2}", triangle="678588"),
            entity("{G3}", triangle="0"),
        ],
    })
    values = provider.sample_field_values(mqs_layer(), "triangle")
    assert values == ["0", "678588"]  # distinct, order preserved


def test_sample_field_values_respects_limit(tmp_path):
    provider, _ = make_provider(tmp_path, lambda request: {
        "next_page": None,
        "entities_list": [entity(str(i), source_id=i) for i in range(50)],
    })
    values = provider.sample_field_values(mqs_layer(), "source_id", limit=5)
    assert len(values) == 5


def test_sample_field_values_unknown_field_returns_empty(tmp_path):
    provider, handler = make_provider(tmp_path, lambda request: {
        "next_page": None, "entities_list": [entity("{G1}")],
    })
    assert provider.sample_field_values(mqs_layer(), "ROAD_NAME") == []
    # Dynamic property_list names are only known after reading entity details.
    assert len(handler.requests) == 2


def test_list_remote_layers(tmp_path):
    provider, handler = make_provider(tmp_path, lambda request: {
        "total_layers": 2,
        "layers_list": [
            {"layer_id": "1", "display_name": "roads"},
            {"layer_id": "2", "display_name": "parks"},
        ],
    })
    layers = provider.list_remote_layers()
    assert [layer["display_name"] for layer in layers] == ["roads", "parks"]
    assert handler.requests[0].url.path == "/MoriaProject/Layers"


def test_list_remote_layers_accepts_bare_array(tmp_path):
    provider, _ = make_provider(tmp_path, lambda request: [
        {"layer_id": "1", "display_name": "roads"},
    ])
    assert provider.list_remote_layers() == [{"layer_id": "1", "display_name": "roads"}]


def test_list_remote_layers_rejects_unknown_200_response(tmp_path):
    provider, _ = make_provider(tmp_path, lambda request: {"success": True})
    with pytest.raises(ProviderError, match="unrecognized layer-list response"):
        provider.list_remote_layers()


def test_full_moria_layer_object_is_normalized(tmp_path):
    provider, _ = make_provider(tmp_path, lambda request: {
        "total_layers": 46,
        "layers_list": [{
            "display_name": "בניינים",
            "name": "B_BUILDINGS",
            "layer_id": "614",
            "layer_entities_link": "https://basef/MQS/MoriaProject/614/Entities",
        }],
    })
    layers, skipped = browse_mqs_layers(provider)
    assert skipped == 0
    assert len(layers) == 1
    assert layers[0].id == "614"
    assert layers[0].name == "בניינים"
    assert layers[0].source_url == "mqs://layer/614"
