import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import httpx
import pytest
from shapely import wkt
from shapely.geometry import box

from app.bl.ports.mqs_mirror import MirroredMqsEntity
from app.common.errors.provider_error import ProviderError
from app.dal.mqs_mirror_store import InMemoryMqsMirrorStore
from app.dal.providers.mqs import MqsProvider
from tests.test_mqs_provider import (
    RecordingHandler,
    entity,
    make_store,
    mqs_layer,
)


class FakeMirror:
    def __init__(self, latest: Optional[List[dict]] = None):
        self.latest = None if latest is None else [
            MirroredMqsEntity(
                geometry=wkt.loads(item["geo"]["wkt"]), entity=item)
            for item in latest
        ]
        self.versions: Dict[str, str] = {}
        self.seen: List[str] = []
        self.upserted: List[dict] = []
        self.completed = False
        self.aborted = False

    def fetch_latest(self, layer_id, geometry, limit):
        return self.latest

    def begin_snapshot(self, layer_id: str) -> str:
        return "run-1"

    def unchanged_ids(
        self, layer_id: str, versions: Sequence[Tuple[str, str]]
    ) -> Set[str]:
        return {entity_id for entity_id, version in versions
                if self.versions.get(entity_id) == version}

    def mark_seen(
        self, layer_id: str, run_id: str, entity_ids: Iterable[str]
    ) -> None:
        self.seen.extend(entity_ids)

    def upsert_entities(self, layer_id, run_id, entities):
        self.upserted.extend(entities)

    def complete_snapshot(self, layer_id: str, run_id: str) -> None:
        self.completed = True

    def abort_snapshot(self, layer_id: str, run_id: str, error: str) -> None:
        self.aborted = True


def _provider(tmp_path, responses, mirror):
    handler = RecordingHandler(responses)
    provider = MqsProvider(
        make_store(tmp_path), transport=httpx.MockTransport(handler),
        mirror=mirror, detail_concurrency=2,
    )
    return provider, handler


def test_latest_mirror_avoids_live_mqs(tmp_path):
    mirrored = entity("G1", property_list={"name": "cached"})
    provider, handler = _provider(
        tmp_path, lambda request: (_ for _ in ()).throw(AssertionError()),
        FakeMirror(latest=[mirrored]),
    )

    result = provider.fetch_features(mqs_layer())

    assert result.iloc[0]["name"] == "cached"
    assert handler.requests == []


def test_missing_snapshot_does_not_trigger_live_mqs(tmp_path):
    provider, handler = _provider(
        tmp_path,
        lambda request: (_ for _ in ()).throw(AssertionError()),
        FakeMirror(latest=None),
    )

    with pytest.raises(ProviderError, match="first snapshot"):
        provider.fetch_features(mqs_layer())

    assert handler.requests == []


def test_snapshot_skips_detail_for_unchanged_history(tmp_path):
    listed = [entity("G1"), entity("G2")]

    def responses(request):
        if request.url.path.endswith("/Entities/G2"):
            return entity("G2", property_list={"name": "changed"})
        if "/Entities/" in request.url.path:
            raise AssertionError("unchanged entity detail should not be fetched")
        return {"next_page": None, "entities_list": listed}

    mirror = FakeMirror()
    mirror.versions["G1"] = "1"
    provider, handler = _provider(tmp_path, responses, mirror)

    count = provider.sync_layer_to_mirror(mqs_layer(), mirror, batch_size=10)

    assert count == 2
    assert mirror.seen == ["G1"]
    assert [item["exclusive_id"]["entity_id"] for item in mirror.upserted] == ["G2"]
    assert mirror.completed is True
    detail_paths = [request.url.path for request in handler.requests
                    if not request.url.path.endswith("/Entities")]
    assert detail_paths == ["/MoriaProject/42/Entities/G2"]


def test_snapshot_prefers_full_data_endpoint_and_avoids_detail_calls(tmp_path):
    full = entity("G1", property_list={"name": "full-data"})

    def responses(request):
        if request.url.path != "/Data/MoriaProject/42/Entities":
            raise AssertionError("full data must not require entity detail")
        return {"next_page": None, "entities_list": [full]}

    mirror = FakeMirror()
    provider, handler = _provider(tmp_path, responses, mirror)

    assert provider.sync_layer_to_mirror(mqs_layer(), mirror, 100) == 1
    request = handler.requests[0]
    assert request.method == "POST"
    assert dict(request.url.params) == {
        "from": "0", "to": "10000", "geo_type": "wkt",
        "result_type": "data",
    }
    match = json.loads(request.content)["filter"]["simple_operators"]["match"]
    assert match["IS_DELETED"] == {"type": "IN", "values": [False]}
    assert mirror.upserted[0]["property_list"]["name"] == "full-data"


def test_snapshot_falls_back_when_full_data_endpoint_is_unsupported(tmp_path):
    full = entity("G1", property_list={"name": "legacy"})

    def responses(request):
        if request.url.path.startswith("/Data/"):
            return httpx.Response(404)
        return {"next_page": None, "entities_list": [full]}

    mirror = FakeMirror()
    provider, handler = _provider(tmp_path, responses, mirror)

    assert provider.sync_layer_to_mirror(mqs_layer(), mirror, 100) == 1
    assert provider.sync_layer_to_mirror(mqs_layer(), mirror, 100) == 1
    assert [request.url.path for request in handler.requests] == [
        "/Data/MoriaProject/42/Entities", "/MoriaProject/42/Entities",
        "/MoriaProject/42/Entities",
    ]


def _complete_snapshot(store, layer_id, entities):
    run_id = store.begin_snapshot(layer_id)
    assert run_id is not None
    store.upsert_entities(layer_id, run_id, entities)
    store.complete_snapshot(layer_id, run_id)


def test_memory_mirror_keeps_multiple_layers_isolated():
    store = InMemoryMqsMirrorStore()
    _complete_snapshot(store, "42", [entity("A", layer_id="42")])
    _complete_snapshot(store, "43", [entity("B", layer_id="43")])

    first = store.fetch_latest("42", None, None)
    second = store.fetch_latest("43", None, None)

    assert [item.entity["exclusive_id"]["entity_id"] for item in first] == ["A"]
    assert [item.entity["exclusive_id"]["entity_id"] for item in second] == ["B"]


def test_memory_mirror_uses_compact_spatial_filter():
    store = InMemoryMqsMirrorStore()
    inside = entity("inside", wkt_value="POINT (34.78 32.08)")
    outside = entity("outside", wkt_value="POINT (35.5 33.0)")
    bbox_only = entity(
        "bbox-only",
        wkt_value=(
            "POLYGON ((34.7 32.0, 34.9 32.0, 34.9 32.2, 34.7 32.2, "
            "34.7 32.0), (34.75 32.05, 34.75 32.195, 34.895 32.195, "
            "34.895 32.05, 34.75 32.05))"
        ),
    )
    _complete_snapshot(store, "42", [inside, outside, bbox_only])

    results = store.fetch_latest(
        "42", box(34.76, 32.06, 34.89, 32.19), None)
    status = store.status(30)[0]

    assert [item.entity["exclusive_id"]["entity_id"] for item in results] == ["inside"]
    assert status["query_count"] == 1
    assert status["last_candidate_count"] == 1
    assert status["last_result_count"] == 1


def test_memory_mirror_serves_latest_snapshot_when_stale():
    store = InMemoryMqsMirrorStore()
    _complete_snapshot(store, "42", [entity("A")])
    store._layers["42"]["completed_at"] = (
        datetime.now(timezone.utc) - timedelta(minutes=5))

    results = store.fetch_latest("42", None, None)
    status = store.status(max_age_seconds=30)[0]

    assert [item.entity["exclusive_id"]["entity_id"] for item in results] == ["A"]
    assert status["fresh"] is False


def test_memory_mirror_snapshot_lock_is_per_layer():
    store = InMemoryMqsMirrorStore()
    first_run = store.begin_snapshot("42")

    assert first_run is not None
    assert store.begin_snapshot("42") is None
    assert store.begin_snapshot("43") is not None

    store.abort_snapshot("42", first_run, "cancelled")
    assert store.begin_snapshot("42") is not None
