"""Parse MQS catalog source URLs."""

from typing import Optional, Tuple

from app.bl.catalog.models.layer_meta import LayerMeta
from app.common.errors.provider_error import ProviderError


class MqsSource:
    _NON_ID_SEGMENTS = ("entities", "layers", "moriaproject")

    def layer_id(self, layer: LayerMeta) -> str:
        segments = [
            segment for segment in layer.source_url.strip().split("/")
            if segment and segment.lower() not in self._NON_ID_SEGMENTS
        ]
        if not segments:
            raise ProviderError(
                f"Layer {layer.id} has no MQS layer id in its source_url "
                f"({layer.source_url!r}) — expected mqs://layer/<id>"
            )
        return segments[-1]

    @staticmethod
    def temporal_field(layer: LayerMeta) -> Optional[str]:
        for tag in layer.tags:
            if tag == "no_temporal_field":
                return None
            if tag.startswith("temporal_field:"):
                return tag[len("temporal_field:"):].strip() or None
        return "date"

    @staticmethod
    def entity_field(layer: LayerMeta) -> Optional[str]:
        return layer.entity_field
