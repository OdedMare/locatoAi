from typing import Protocol

from app.bl.ports.layer_meta import LayerMeta
from app.bl.ports.mqs_mirror import MqsMirror


class MqsSnapshotSource(Protocol):
    def sync_layer_to_mirror(
        self, layer: LayerMeta, mirror: MqsMirror, batch_size: int
    ) -> int: ...
