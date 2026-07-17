"""Shared PostgreSQL connection factory driven by live runtime settings."""

import psycopg
from psycopg.rows import dict_row

from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore


class PostgresConnection:
    @classmethod
    def connect(cls, store: RuntimeSettingsStore) -> psycopg.Connection:
        settings = store.get()
        return psycopg.connect(
            settings.database_url,
            row_factory=dict_row,
            **cls._credentials(settings),
        )

    @staticmethod
    def _credentials(settings) -> dict:
        optional = {
            "user": settings.database_user,
            "password": settings.database_password,
            "host": settings.database_host,
            "dbname": settings.database_name,
        }
        credentials = {key: value for key, value in optional.items() if value}
        if settings.database_port is not None:
            credentials["port"] = settings.database_port
        return credentials


connect = PostgresConnection.connect
