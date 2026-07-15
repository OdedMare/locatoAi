"""PostGIS read model for the current MQS entity snapshot."""

import json
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Iterable, List, Optional, Sequence, Set, Tuple
from uuid import uuid4

from shapely import wkt
from shapely.geometry.base import BaseGeometry

from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.postgres import connect

_FEATURES_TABLE = "public.mqs_feature_mirror"
_STATE_TABLE = "public.mqs_mirror_state"


def _exclusive_id(entity: dict) -> dict:
    value = entity.get("exclusive_id")
    return value if isinstance(value, dict) else {}


def _entity_id(entity: dict) -> Optional[str]:
    value = _exclusive_id(entity).get("entity_id") or entity.get("entity_id")
    return str(value) if value is not None else None


def _history_id(entity: dict) -> str:
    value = _exclusive_id(entity).get("history_id")
    return "" if value is None else str(value)


def _geometry_wkt(entity: dict) -> Optional[str]:
    geo = entity.get("geo")
    value = geo.get("wkt") if isinstance(geo, dict) else None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return wkt.loads(value).wkt
    except Exception:
        return None


class PostgresMqsMirrorStore:
    def __init__(self, settings_store: RuntimeSettingsStore):
        self._store = settings_store
        self._ready = False
        self._locks = {}
        self._schema_lock = Lock()
        self._locks_guard = Lock()

    def ensure_schema(self) -> None:
        if self._ready:
            return
        with self._schema_lock:
            if self._ready:
                return
            with connect(self._store) as conn:
                conn.execute(self._features_ddl())
                conn.execute(self._state_ddl())
                conn.execute(self._spatial_index_ddl())
            self._ready = True

    @staticmethod
    def _features_ddl() -> str:
        return f"""CREATE TABLE IF NOT EXISTS {_FEATURES_TABLE} (
            layer_id text NOT NULL, entity_id text NOT NULL,
            history_id text NOT NULL DEFAULT '', payload jsonb NOT NULL,
            geometry geometry(Geometry, 4326), sync_run text NOT NULL,
            mirrored_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (layer_id, entity_id))"""

    @staticmethod
    def _state_ddl() -> str:
        return f"""CREATE TABLE IF NOT EXISTS {_STATE_TABLE} (
            layer_id text PRIMARY KEY, active_run text,
            last_completed_at timestamptz, last_error text)"""

    @staticmethod
    def _spatial_index_ddl() -> str:
        return (
            "CREATE INDEX IF NOT EXISTS mqs_feature_mirror_geometry_gix "
            f"ON {_FEATURES_TABLE} USING gist (geometry)"
        )

    def fetch_fresh(
        self, layer_id: str, geometry: Optional[BaseGeometry],
        max_age_seconds: int, limit: Optional[int],
    ) -> Optional[List[dict]]:
        self.ensure_schema()
        if not self._is_fresh(layer_id, max_age_seconds):
            return None
        query, params = self._fetch_query(layer_id, geometry, limit)
        with connect(self._store) as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._payload(row["payload"]) for row in rows]

    def _is_fresh(self, layer_id: str, max_age_seconds: int) -> bool:
        threshold = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
        with connect(self._store) as conn:
            row = conn.execute(
                f"SELECT last_completed_at FROM {_STATE_TABLE} WHERE layer_id = %s",
                (layer_id,),
            ).fetchone()
        return bool(row and row["last_completed_at"] >= threshold)

    @staticmethod
    def _fetch_query(layer_id, geometry, limit):
        query = f"SELECT payload FROM {_FEATURES_TABLE} WHERE layer_id = %s"
        params: List[object] = [layer_id]
        if geometry is not None:
            query += " AND ST_Intersects(geometry, ST_GeomFromText(%s, 4326))"
            params.append(geometry.wkt)
        query += " ORDER BY entity_id"
        if limit is not None:
            query += " LIMIT %s"
            params.append(limit)
        return query, tuple(params)

    @staticmethod
    def _payload(value) -> dict:
        return json.loads(value) if isinstance(value, str) else value

    def begin_snapshot(self, layer_id: str) -> Optional[str]:
        self.ensure_schema()
        run_id = str(uuid4())
        lock_connection = connect(self._store)
        if not self._acquire_lock(lock_connection, layer_id):
            lock_connection.close()
            return None
        try:
            self._record_snapshot_start(layer_id, run_id)
        except Exception:
            lock_connection.close()
            raise
        with self._locks_guard:
            self._locks[run_id] = lock_connection
        return run_id

    @staticmethod
    def _acquire_lock(connection, layer_id: str) -> bool:
        row = connection.execute(
            "SELECT pg_try_advisory_lock(hashtextextended(%s, 0)) AS acquired",
            (layer_id,),
        ).fetchone()
        return bool(row and row["acquired"])

    def _record_snapshot_start(self, layer_id: str, run_id: str) -> None:
        with connect(self._store) as conn:
            conn.execute(
                f"""INSERT INTO {_STATE_TABLE} (layer_id, active_run, last_error)
                VALUES (%s, %s, NULL) ON CONFLICT (layer_id) DO UPDATE SET
                active_run = EXCLUDED.active_run, last_error = NULL""",
                (layer_id, run_id),
            )

    def unchanged_ids(
        self, layer_id: str, versions: Sequence[Tuple[str, str]]
    ) -> Set[str]:
        if not versions:
            return set()
        entity_ids = [item[0] for item in versions]
        expected = dict(versions)
        with connect(self._store) as conn:
            rows = conn.execute(
                f"""SELECT entity_id, history_id FROM {_FEATURES_TABLE}
                WHERE layer_id = %s AND entity_id = ANY(%s)""",
                (layer_id, entity_ids),
            ).fetchall()
        return {row["entity_id"] for row in rows
                if row["history_id"] == expected[row["entity_id"]]}

    def mark_seen(
        self, layer_id: str, run_id: str, entity_ids: Iterable[str]
    ) -> None:
        ids = list(entity_ids)
        if not ids:
            return
        with connect(self._store) as conn:
            conn.execute(
                f"""UPDATE {_FEATURES_TABLE} SET sync_run = %s,
                mirrored_at = now() WHERE layer_id = %s AND entity_id = ANY(%s)""",
                (run_id, layer_id, ids),
            )

    def upsert_entities(
        self, layer_id: str, run_id: str, entities: Sequence[dict]
    ) -> None:
        rows = [self._entity_row(layer_id, run_id, entity) for entity in entities]
        rows = [row for row in rows if row is not None]
        if not rows:
            return
        with connect(self._store) as conn:
            conn.executemany(self._upsert_sql(), rows)

    @staticmethod
    def _entity_row(layer_id: str, run_id: str, entity: dict):
        entity_id = _entity_id(entity)
        if entity_id is None:
            return None
        return (layer_id, entity_id, _history_id(entity),
                json.dumps(entity, ensure_ascii=False, default=str),
                _geometry_wkt(entity), run_id)

    @staticmethod
    def _upsert_sql() -> str:
        return f"""INSERT INTO {_FEATURES_TABLE}
            (layer_id, entity_id, history_id, payload, geometry, sync_run)
            VALUES (%s, %s, %s, %s::jsonb, ST_GeomFromText(%s, 4326), %s)
            ON CONFLICT (layer_id, entity_id) DO UPDATE SET
            history_id = EXCLUDED.history_id, payload = EXCLUDED.payload,
            geometry = EXCLUDED.geometry, sync_run = EXCLUDED.sync_run,
            mirrored_at = now()"""

    def complete_snapshot(self, layer_id: str, run_id: str) -> None:
        try:
            with connect(self._store) as conn:
                conn.execute(
                    f"DELETE FROM {_FEATURES_TABLE} WHERE layer_id = %s AND sync_run <> %s",
                    (layer_id, run_id),
                )
                conn.execute(
                    f"""UPDATE {_STATE_TABLE} SET active_run = NULL,
                    last_completed_at = now(), last_error = NULL
                    WHERE layer_id = %s AND active_run = %s""",
                    (layer_id, run_id),
                )
        finally:
            self._release_lock(run_id)

    def abort_snapshot(self, layer_id: str, run_id: str, error: str) -> None:
        try:
            with connect(self._store) as conn:
                conn.execute(
                    f"""UPDATE {_STATE_TABLE} SET active_run = NULL, last_error = %s
                    WHERE layer_id = %s AND active_run = %s""",
                    (error[:2000], layer_id, run_id),
                )
        finally:
            self._release_lock(run_id)

    def _release_lock(self, run_id: str) -> None:
        with self._locks_guard:
            connection = self._locks.pop(run_id, None)
        if connection is not None:
            connection.close()
