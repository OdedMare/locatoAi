"""PostgreSQL persistence for user feedback."""

import json
from datetime import datetime
from typing import List, Optional

from app.common.runtime_settings import RuntimeSettingsStore
from app.dal.postgres import connect


class PostgresFeedbackRepository:
    def __init__(self, settings_store: RuntimeSettingsStore):
        self._store = settings_store

    def add(
        self,
        query: str,
        verdict: str,
        selected_layers: List[str],
        reasoning: str,
        clarify: Optional[str],
        timestamp: datetime,
    ) -> None:
        table = self._store.get().quoted_feedback_table()
        with connect(self._store) as conn:
            conn.execute(
                f"CREATE TABLE IF NOT EXISTS {table} ("
                "id BIGSERIAL PRIMARY KEY, "
                "query TEXT NOT NULL, "
                "verdict TEXT NOT NULL CHECK (verdict IN ('up', 'down')), "
                "selected_layers JSONB NOT NULL DEFAULT '[]'::jsonb, "
                "reasoning TEXT NOT NULL DEFAULT '', "
                "clarify TEXT, "
                "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
                ")"
            )
            conn.execute(
                f"INSERT INTO {table} "
                "(query, verdict, selected_layers, reasoning, clarify, created_at) "
                "VALUES (%s, %s, %s::jsonb, %s, %s, %s)",
                (
                    query,
                    verdict,
                    json.dumps(selected_layers, ensure_ascii=False),
                    reasoning,
                    clarify,
                    timestamp,
                ),
            )
