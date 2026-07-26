from typing import List, Optional, Tuple

from app.bl.catalog.mqs_sync.remote_mqs_layer import RemoteMqsLayer

_ID_KEYS = ("id", "layerId", "layer_id", "Id")
_NAME_KEYS = ("display_name", "name", "title", "alias", "Name")
_DESCRIPTION_KEYS = (
    "unclassified_description", "description", "comments", "Description"
)
_TAG_KEYS = ("tags", "category", "group")

_MAX_NAME = 200
_MAX_DESCRIPTION = 2000
_MAX_TAGS = 20


class MqsLayerBrowser:
    def browse(self, mqs_provider) -> Tuple[List[RemoteMqsLayer], int]:
        layers: List[RemoteMqsLayer] = []
        skipped = 0
        seen = set()
        for entry in mqs_provider.list_remote_layers():
            layer = self._normalize(entry, seen)
            if layer is None:
                skipped += 1
            else:
                layers.append(layer)
        return layers, skipped

    def _normalize(self, entry: object, seen: set) -> Optional[RemoteMqsLayer]:
        if not isinstance(entry, dict):
            return None
        layer_id = self._normalized_id(entry)
        if not layer_id or layer_id in seen:
            return None
        seen.add(layer_id)
        return self._remote_layer(entry, layer_id)

    def _remote_layer(self, entry: dict, layer_id: str) -> RemoteMqsLayer:
        name = self._first(entry, _NAME_KEYS)
        description = self._first(entry, _DESCRIPTION_KEYS)
        return RemoteMqsLayer(
            id=layer_id,
            name=(str(name).strip() if name else f"MQS layer {layer_id}")[:_MAX_NAME],
            description=(str(description).strip() if description else "")[:_MAX_DESCRIPTION],
            tags=self._tags(entry),
        )

    def _normalized_id(self, entry: dict) -> Optional[str]:
        value = self._layer_id(entry)
        return str(value).strip() if value is not None else None

    def _layer_id(self, entry: dict) -> Optional[object]:
        direct = self._first(entry, _ID_KEYS)
        if direct is not None:
            return direct
        exclusive_id = entry.get("exclusive_id")
        return self._first(exclusive_id, _ID_KEYS) if isinstance(exclusive_id, dict) else None

    def _tags(self, entry: dict) -> List[str]:
        raw = self._first(entry, _TAG_KEYS)
        if isinstance(raw, str):
            raw = [raw]
        if not isinstance(raw, list):
            return []
        cleaned = [tag.strip() for tag in raw if isinstance(tag, str) and tag.strip()]
        return list(dict.fromkeys(cleaned))[:_MAX_TAGS]

    @staticmethod
    def _first(entry: dict, keys) -> Optional[object]:
        return next(
            (entry[key] for key in keys if key in entry and entry[key] not in (None, "")),
            None,
        )


browse_mqs_layers = MqsLayerBrowser().browse
