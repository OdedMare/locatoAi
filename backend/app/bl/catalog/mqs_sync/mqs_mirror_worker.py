"""Continuous MQS snapshot refresher, isolated from request threads."""

import logging
from threading import Event, Thread
from typing import List

from app.bl.catalog.catalog_service import CatalogService
from app.bl.ports.layer_meta import LayerMeta
from app.bl.ports.mqs_mirror import MqsMirror
from app.bl.ports.mqs_snapshot_source import MqsSnapshotSource

logger = logging.getLogger(__name__)


class MqsMirrorWorker:
    def __init__(self, catalog: CatalogService, source: MqsSnapshotSource,
                 mirror: MqsMirror, interval_seconds: int, batch_size: int):
        self._catalog = catalog
        self._source = source
        self._mirror = mirror
        self._interval = max(1, interval_seconds)
        self._batch_size = max(1, batch_size)
        self._stop = Event()
        self._thread = Thread(target=self._run, name="mqs-mirror", daemon=True)

    def start(self) -> None:
        if not self._thread.is_alive():
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop.is_set():
            self._sync_layers(self._mqs_layers())
            self._stop.wait(self._interval)

    def _mqs_layers(self) -> List[LayerMeta]:
        try:
            return [layer for layer in self._catalog.list_layers()
                    if layer.provider == "mqs"]
        except Exception:
            logger.exception("MQS mirror failed to list catalog layers")
            return []

    def _sync_layers(self, layers: List[LayerMeta]) -> None:
        for layer in layers:
            if self._stop.is_set():
                return
            try:
                count = self._source.sync_layer_to_mirror(
                    layer, self._mirror, self._batch_size)
                logger.info("MQS mirror layer=%s entities=%d", layer.id, count)
            except Exception:
                logger.exception("MQS mirror failed layer=%s", layer.id)
