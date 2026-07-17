"""Map raw LLM layer-selection JSON into the domain result."""

from app.bl.agent.select_layers.layer_selection import LayerSelection


class LayerSelectionMapper:
    FALLBACK_CLARIFY = "לא הצלחתי להתאים שכבת מידע לבקשה — אפשר לנסח מחדש?"

    def from_response(self, data: dict, layers) -> LayerSelection:
        usage = data.get("_usage")
        usage = usage if isinstance(usage, dict) else None
        reasoning = data.get("reasoning")
        reasoning = reasoning.strip() if isinstance(reasoning, str) else ""
        requested = self._requested_ids(data)
        picked, dropped = self._resolve(requested, layers)
        if picked:
            return LayerSelection(
                layers=picked, reasoning=reasoning, token_usage=usage,
                requested_layer_ids=requested, dropped_layer_ids=dropped,
            )
        return LayerSelection(
            clarify=self._clarify(data), reasoning=reasoning, token_usage=usage,
            requested_layer_ids=requested, dropped_layer_ids=dropped,
        )

    @staticmethod
    def _requested_ids(data: dict):
        raw_ids = data.get("layer_ids") or []
        return [str(layer_id) for layer_id in raw_ids] if isinstance(raw_ids, list) else []

    @staticmethod
    def _resolve(requested, layers):
        by_id = {layer.id: layer for layer in layers}
        unique = list(dict.fromkeys(requested))
        picked = [by_id[layer_id] for layer_id in unique if layer_id in by_id]
        dropped = [layer_id for layer_id in unique if layer_id not in by_id]
        return picked, dropped

    def _clarify(self, data: dict) -> str:
        clarify = data.get("clarify")
        if not isinstance(clarify, str) or not clarify.strip():
            return self.FALLBACK_CLARIFY
        return clarify.strip()
