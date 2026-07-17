"""Normalize common OpenAI-compatible model-list payloads."""


class ModelIdExtractor:
    @classmethod
    def extract(cls, payload) -> list:
        items = cls._items(payload)
        if not isinstance(items, list):
            return []
        identifiers = {identifier for item in items
                       for identifier in [cls._identifier(item)] if identifier}
        return sorted(identifiers)

    @staticmethod
    def _items(payload):
        if not isinstance(payload, dict):
            return payload
        data = payload.get("data")
        return data if data is not None else payload.get("models")

    @staticmethod
    def _identifier(item):
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            value = item.get("id") or item.get("name") or item.get("model")
            return str(value) if value else None
        return None
