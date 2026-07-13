"""Sync the MQS layer inventory into the local catalog.

GET /MoriaProject/Layers → one catalog row per remote layer, keyed by
(provider='mqs', source_url='mqs://layer/{id}') so re-syncs update in
place instead of duplicating. Updates touch name/description only —
tags are preserved because scripts/enrich_layer_tags.py may have
enriched them after the first sync (rerun it after syncing new layers).

Remote metadata is untrusted: hygiene here is caps/dedup only —
prompt-injection sanitization stays at prompt-build time (locked rule).
"""

from dataclasses import dataclass
from typing import List, Optional
from uuid import uuid4

from app.bl.ports import LayerMeta, LayersRepository

_ID_KEYS = ("id", "layerId", "layer_id", "Id")
_NAME_KEYS = ("name", "title", "alias", "Name")
_DESCRIPTION_KEYS = ("description", "comments", "Description")
_TAG_KEYS = ("tags", "category", "group")

_MAX_NAME = 200
_MAX_DESCRIPTION = 2000
_MAX_TAGS = 20


@dataclass
class MqsSyncResult:
    added: int = 0
    updated: int = 0
    skipped: int = 0

    @property
    def total(self) -> int:
        return self.added + self.updated + self.skipped


def _first(entry: dict, keys) -> Optional[object]:
    for key in keys:
        if key in entry and entry[key] not in (None, ""):
            return entry[key]
    return None


def _tags(entry: dict) -> List[str]:
    raw = _first(entry, _TAG_KEYS)
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    cleaned = [tag.strip() for tag in raw if isinstance(tag, str) and tag.strip()]
    return list(dict.fromkeys(cleaned))[:_MAX_TAGS]


def sync_mqs_layers(repository: LayersRepository, mqs_provider) -> MqsSyncResult:
    """`mqs_provider` is duck-typed: anything with list_remote_layers()."""
    result = MqsSyncResult()
    for entry in mqs_provider.list_remote_layers():
        layer_id = _first(entry, _ID_KEYS)
        if layer_id is None:
            result.skipped += 1
            continue
        name = _first(entry, _NAME_KEYS)
        description = _first(entry, _DESCRIPTION_KEYS)
        layer = LayerMeta(
            id=str(uuid4()),  # replaced by the repository on insert
            name=(str(name).strip() if name else f"MQS layer {layer_id}")[:_MAX_NAME],
            description=(str(description).strip() if description else "")[
                :_MAX_DESCRIPTION
            ],
            tags=_tags(entry),  # only applied on insert; updates preserve tags
            provider="mqs",
            source_url=f"mqs://layer/{layer_id}",
        )
        _, created = repository.upsert_layer(layer)
        if created:
            result.added += 1
        else:
            result.updated += 1
    return result
