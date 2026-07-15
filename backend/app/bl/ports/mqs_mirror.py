from typing import Iterable, List, Optional, Protocol, Sequence, Set, Tuple

from shapely.geometry.base import BaseGeometry


class MqsMirror(Protocol):
    """Persistent, queryable read model for MQS entities."""

    def fetch_fresh(
        self,
        layer_id: str,
        geometry: Optional[BaseGeometry],
        max_age_seconds: int,
        limit: Optional[int],
    ) -> Optional[List[dict]]: ...

    def begin_snapshot(self, layer_id: str) -> str: ...

    def unchanged_ids(
        self, layer_id: str, versions: Sequence[Tuple[str, str]]
    ) -> Set[str]: ...

    def mark_seen(self, layer_id: str, run_id: str, entity_ids: Iterable[str]) -> None: ...

    def upsert_entities(
        self, layer_id: str, run_id: str, entities: Sequence[dict]
    ) -> None: ...

    def complete_snapshot(self, layer_id: str, run_id: str) -> None: ...

    def abort_snapshot(self, layer_id: str, run_id: str, error: str) -> None: ...
