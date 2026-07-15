from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Protocol, Sequence, Set, Tuple

from shapely.geometry.base import BaseGeometry


@dataclass(frozen=True)
class MirroredMqsEntity:
    """Decoded MQS payload paired with its already-parsed geometry."""

    geometry: BaseGeometry
    entity: Dict[str, object]


class MqsMirror(Protocol):
    """Queryable read model for the latest completed MQS snapshot."""

    def fetch_latest(
        self,
        layer_id: str,
        geometry: Optional[BaseGeometry],
        limit: Optional[int],
    ) -> Optional[List[MirroredMqsEntity]]: ...

    def status(self, max_age_seconds: int) -> List[dict]: ...

    def begin_snapshot(self, layer_id: str) -> Optional[str]: ...

    def unchanged_ids(
        self, layer_id: str, versions: Sequence[Tuple[str, str]]
    ) -> Set[str]: ...

    def mark_seen(self, layer_id: str, run_id: str, entity_ids: Iterable[str]) -> None: ...

    def upsert_entities(
        self, layer_id: str, run_id: str, entities: Sequence[dict]
    ) -> None: ...

    def complete_snapshot(self, layer_id: str, run_id: str) -> None: ...

    def abort_snapshot(self, layer_id: str, run_id: str, error: str) -> None: ...
