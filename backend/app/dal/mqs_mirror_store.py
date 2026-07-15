"""Compressed in-process read model for MQS entity snapshots."""

import json
import zlib
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Iterable, List, Optional, Sequence, Set, Tuple
from uuid import uuid4

import numpy as np
from shapely import wkb, wkt
from shapely.geometry.base import BaseGeometry


def _exclusive_id(entity: dict) -> dict:
    value = entity.get("exclusive_id")
    return value if isinstance(value, dict) else {}


def _entity_id(entity: dict) -> Optional[str]:
    value = _exclusive_id(entity).get("entity_id") or entity.get("entity_id")
    return str(value) if value is not None else None


def _history_id(entity: dict) -> str:
    value = _exclusive_id(entity).get("history_id")
    return "" if value is None else str(value)


def _geometry(entity: dict) -> Optional[BaseGeometry]:
    geo = entity.get("geo")
    value = geo.get("wkt") if isinstance(geo, dict) else None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return wkt.loads(value)
    except Exception:
        return None


def _compressed_payload(entity: dict) -> bytes:
    raw = json.dumps(entity, ensure_ascii=False, default=str).encode("utf-8")
    return zlib.compress(raw, level=3)


def _payload(value: bytes) -> dict:
    return json.loads(zlib.decompress(value).decode("utf-8"))


class InMemoryMqsMirrorStore:
    """Atomic per-layer snapshots with compact spatial candidate arrays."""

    def __init__(self):
        self._guard = RLock()
        self._layers = {}
        self._runs = {}
        self._active_runs = {}
        self._last_errors = {}

    def fetch_fresh(
        self, layer_id: str, geometry: Optional[BaseGeometry],
        max_age_seconds: int, limit: Optional[int],
    ) -> Optional[List[dict]]:
        with self._guard:
            snapshot = self._layers.get(layer_id)
        if not self._is_fresh(snapshot, max_age_seconds):
            return None
        indexes = self._candidate_indexes(snapshot, geometry)
        return self._matching_payloads(snapshot, indexes, geometry, limit)

    @staticmethod
    def _is_fresh(snapshot, max_age_seconds: int) -> bool:
        if snapshot is None:
            return False
        age = datetime.now(timezone.utc) - snapshot["completed_at"]
        return age <= timedelta(seconds=max_age_seconds)

    @staticmethod
    def _candidate_indexes(snapshot, geometry):
        if geometry is None:
            return range(len(snapshot["ids"]))
        min_x, min_y, max_x, max_y = geometry.bounds
        bounds = snapshot["bounds"]
        mask = ((bounds[:, 0] <= max_x) & (bounds[:, 1] >= min_x)
                & (bounds[:, 2] <= max_y) & (bounds[:, 3] >= min_y))
        return np.flatnonzero(mask)

    @staticmethod
    def _matching_payloads(snapshot, indexes, geometry, limit):
        results = []
        for index in indexes:
            record = snapshot["records"][snapshot["ids"][int(index)]]
            candidate = wkb.loads(record[2]) if geometry is not None else None
            if geometry is None or candidate.intersects(geometry):
                results.append(_payload(record[1]))
            if limit is not None and len(results) >= limit:
                break
        return results

    def status(self, max_age_seconds: int) -> List[dict]:
        with self._guard:
            layer_ids = sorted(set(self._layers) | set(self._active_runs)
                               | set(self._last_errors))
            return [self._status_row(layer_id, max_age_seconds)
                    for layer_id in layer_ids]

    def _status_row(self, layer_id: str, max_age_seconds: int) -> dict:
        snapshot = self._layers.get(layer_id)
        completed = snapshot["completed_at"] if snapshot is not None else None
        lag = ((datetime.now(timezone.utc) - completed).total_seconds()
               if completed is not None else None)
        return {
            "layer_id": layer_id,
            "active_run": self._active_runs.get(layer_id),
            "last_completed_at": completed,
            "last_error": self._last_errors.get(layer_id),
            "entity_count": len(snapshot["records"]) if snapshot is not None else 0,
            "lag_seconds": None if lag is None else round(lag, 3),
            "fresh": lag is not None and lag <= max_age_seconds,
            "storage": "compressed_memory",
        }

    def begin_snapshot(self, layer_id: str) -> Optional[str]:
        with self._guard:
            if layer_id in self._active_runs:
                return None
            run_id = str(uuid4())
            self._active_runs[layer_id] = run_id
            self._runs[run_id] = {"layer_id": layer_id, "records": {}}
            self._last_errors.pop(layer_id, None)
            return run_id

    def unchanged_ids(
        self, layer_id: str, versions: Sequence[Tuple[str, str]]
    ) -> Set[str]:
        with self._guard:
            snapshot = self._layers.get(layer_id)
            records = snapshot["records"] if snapshot is not None else {}
            return {entity_id for entity_id, version in versions
                    if entity_id in records and records[entity_id][0] == version}

    def mark_seen(
        self, layer_id: str, run_id: str, entity_ids: Iterable[str]
    ) -> None:
        with self._guard:
            run = self._required_run(layer_id, run_id)
            current = self._layers.get(layer_id)
            records = current["records"] if current is not None else {}
            run["records"].update(
                (entity_id, records[entity_id]) for entity_id in entity_ids
                if entity_id in records)

    def upsert_entities(
        self, layer_id: str, run_id: str, entities: Sequence[dict]
    ) -> None:
        records = [self._entity_record(entity) for entity in entities]
        records = [record for record in records if record is not None]
        with self._guard:
            run = self._required_run(layer_id, run_id)
            run["records"].update(records)

    @staticmethod
    def _entity_record(entity: dict):
        entity_id = _entity_id(entity)
        geometry = _geometry(entity)
        if entity_id is None or geometry is None:
            return None
        min_x, min_y, max_x, max_y = geometry.bounds
        record = (_history_id(entity), _compressed_payload(entity), geometry.wkb,
                  (min_x, max_x, min_y, max_y))
        return entity_id, record

    def complete_snapshot(self, layer_id: str, run_id: str) -> None:
        with self._guard:
            run = self._required_run(layer_id, run_id)
            records = run["records"]
        ids = tuple(sorted(records))
        bounds = np.asarray([records[entity_id][3] for entity_id in ids], dtype="f8")
        if not len(ids):
            bounds = np.empty((0, 4), dtype="f8")
        snapshot = {"records": records, "ids": ids, "bounds": bounds,
                    "completed_at": datetime.now(timezone.utc)}
        with self._guard:
            self._layers[layer_id] = snapshot
            self._finish_run(layer_id, run_id)

    def abort_snapshot(self, layer_id: str, run_id: str, error: str) -> None:
        with self._guard:
            self._last_errors[layer_id] = error[:2000]
            self._finish_run(layer_id, run_id)

    def _required_run(self, layer_id: str, run_id: str):
        run = self._runs.get(run_id)
        if run is None or run["layer_id"] != layer_id:
            raise RuntimeError("MQS mirror snapshot is not active")
        return run

    def _finish_run(self, layer_id: str, run_id: str) -> None:
        self._runs.pop(run_id, None)
        if self._active_runs.get(layer_id) == run_id:
            self._active_runs.pop(layer_id, None)
