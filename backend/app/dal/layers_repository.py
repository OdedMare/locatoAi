"""Postgres-backed catalog repository.

Implements the bl.ports.LayersRepository protocol. The only module that
speaks SQL — everything above sees LayerMeta objects.

Connection URL and table name come from the runtime settings store on
every call, so UI settings changes apply without a restart. The table
identifier is validated + quoted by the store (never raw user input).
"""

import psycopg
from psycopg.rows import dict_row

from app.bl.ports import LayerMeta
from app.common.runtime_settings import RuntimeSettingsStore

_COLUMNS = "id, name, description, tags, provider, source_url"


class PostgresLayersRepository:
    def __init__(self, settings_store: RuntimeSettingsStore):
        self._store = settings_store

    def _connect(self) -> psycopg.Connection:
        # MVP: connection per call. Pooling (psycopg_pool) when load justifies it.
        return psycopg.connect(self._store.get().database_url, row_factory=dict_row)

    def _select(self) -> str:
        return f"SELECT {_COLUMNS} FROM {self._store.get().quoted_layers_table()}"

    def list_layers(self) -> list[LayerMeta]:
        with self._connect() as conn:
            rows = conn.execute(self._select()).fetchall()
        return [self._to_meta(row) for row in rows]

    def get_layer(self, layer_id: str) -> LayerMeta | None:
        with self._connect() as conn:
            row = conn.execute(
                self._select() + " WHERE id = %s", (layer_id,)
            ).fetchone()
        return self._to_meta(row) if row else None

    @staticmethod
    def _to_meta(row: dict) -> LayerMeta:
        return LayerMeta(
            id=str(row["id"]),
            name=row["name"],
            description=row["description"] or "",
            tags=row["tags"] or [],
            provider=row["provider"],
            source_url=row["source_url"],
        )
