from typing import List, Optional, Protocol, Tuple

from app.bl.catalog.models.layer_meta import LayerMeta


class LayersRepository(Protocol):
    """Catalog store implemented by the DAL catalog context."""

    def list_layers(self) -> List[LayerMeta]: ...

    def get_layer(self, layer_id: str) -> Optional[LayerMeta]: ...

    def add_layer(self, layer: LayerMeta) -> LayerMeta: ...

    def update_layer_metadata(
        self, layer_id: str, name: str, description: str, tags: List[str],
    ) -> LayerMeta: ...

    def upsert_layer(self, layer: LayerMeta) -> Tuple[LayerMeta, bool]:
        """Insert or update by (provider, source_url); returns (layer, created).
        Updates touch name/description only — tags may be LLM-enriched."""
        ...
