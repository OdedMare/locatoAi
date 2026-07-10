"""Postgres-backed catalog repository.

Implements the bl.ports.LayersRepository protocol. The only module that
speaks SQL — everything above sees LayerMeta objects.

Connection URL and table name come from the runtime settings store on
every call, so UI settings changes apply without a restart. The table
identifier is validated + quoted by the store (never raw user input).
"""

from typing import List, Optional

import psycopg
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row

from app.bl.ports import LayerMeta
from app.common.runtime_settings import RuntimeSettingsStore

_COLUMNS = "id, name, description, tags, provider, source_url"


class PostgresLayersRepository:
    def __init__(self, settings_store: RuntimeSettingsStore):
        self._store = settings_store

    def _connect(self) -> psycopg.Connection:
        # MVP: connection per call. Pooling (psycopg_pool) when load justifies it.
        settings = self._store.get()
        credentials = {}
        if settings.database_user:
            credentials["user"] = settings.database_user
        if settings.database_password:
            credentials["password"] = settings.database_password
        return psycopg.connect(
            settings.database_url,
            row_factory=dict_row,
            **credentials,
        )

    def _select(self) -> str:
        return f"SELECT {_COLUMNS} FROM {self._store.get().quoted_layers_table()}"

    def list_layers(self) -> List[LayerMeta]:
        with self._connect() as conn:
            rows = conn.execute(self._select()).fetchall()
        return [self._to_meta(row) for row in rows]

    def get_layer(self, layer_id: str) -> Optional[LayerMeta]:
        with self._connect() as conn:
            row = conn.execute(
                self._select() + " WHERE id = %s", (layer_id,)
            ).fetchone()
        return self._to_meta(row) if row else None

    def add_layer(self, layer: LayerMeta) -> LayerMeta:
        settings = self._store.get()
        query = (
            f"INSERT INTO {settings.quoted_layers_table()} "
            "(id, name, description, tags, provider, source_url) "
            "VALUES (%s, %s, %s, %s, %s, %s)"
        )
        try:
            with self._connect() as conn:
                conn.execute(
                    query,
                    (
                        layer.id,
                        layer.name,
                        layer.description,
                        layer.tags,
                        layer.provider,
                        layer.source_url,
                    ),
                )
        except UniqueViolation as exc:
            raise ValueError("A layer with this id already exists") from exc
        return layer

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
