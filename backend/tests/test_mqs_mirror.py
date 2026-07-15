from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import httpx

from app.dal.providers.mqs import MqsProvider
from tests.test_mqs_provider import (
    RecordingHandler,
    entity,
    make_store,
    mqs_layer,
)


class FakeMirror:
    def __init__(self, fresh: Optional[List[dict]] = None):
        self.fresh = fresh
        self.versions: Dict[str, str] = {}
        self.seen: List[str] = []
        self.upserted: List[dict] = []
        self.completed = False
        self.aborted = False

    def fetch_fresh(self, layer_id, geometry, max_age_seconds, limit):
        return self.fresh

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


def test_fresh_mirror_avoids_live_mqs(tmp_path):
    mirrored = entity("G1", property_list={"name": "cached"})
    provider, handler = _provider(
        tmp_path, lambda request: (_ for _ in ()).throw(AssertionError()),
        FakeMirror(fresh=[mirrored]),
    )

    result = provider.fetch_features(mqs_layer())

    assert result.iloc[0]["name"] == "cached"
    assert handler.requests == []


def test_stale_mirror_falls_back_to_live_mqs(tmp_path):
    provider, handler = _provider(
        tmp_path,
        lambda request: {"next_page": None, "entities_list": [
            entity("G1", property_list={"name": "live"})]},
        FakeMirror(fresh=None),
    )

    result = provider.fetch_features(mqs_layer())

    assert result.iloc[0]["name"] == "live"
    assert len(handler.requests) == 1


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
