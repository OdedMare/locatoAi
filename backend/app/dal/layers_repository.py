"""Postgres-backed catalog repository (public.layers in the gis DB).

Implements the bl.ports.LayersRepository protocol. The only module that
speaks SQL — everything above sees LayerMeta objects.
"""

import psycopg
from psycopg.rows import dict_row

from app.bl.ports import LayerMeta

_SELECT = "SELECT id, name, description, tags, provider, source_url FROM public.layers"


class PostgresLayersRepository:
    def __init__(self, database_url: str):
        self._database_url = database_url

    def _connect(self) -> psycopg.Connection:
        # MVP: connection per call. Pooling (psycopg_pool) when load justifies it.
        return psycopg.connect(self._database_url, row_factory=dict_row)

    def list_layers(self) -> list[LayerMeta]:
        with self._connect() as conn:
            rows = conn.execute(_SELECT).fetchall()
        return [self._to_meta(row) for row in rows]

    def get_layer(self, layer_id: str) -> LayerMeta | None:
        with self._connect() as conn:
            row = conn.execute(_SELECT + " WHERE id = %s", (layer_id,)).fetchone()
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
