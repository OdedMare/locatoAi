"""Shared PostgreSQL connection factory driven by live runtime settings."""

import psycopg
from psycopg.rows import dict_row

from app.common.runtime_settings import RuntimeSettingsStore


def connect(store: RuntimeSettingsStore) -> psycopg.Connection:
    """Connect using the same URL and optional overrides used by all DALs."""
    settings = store.get()
    credentials = {}
    if settings.database_user:
        credentials["user"] = settings.database_user
    if settings.database_password:
        credentials["password"] = settings.database_password
    if settings.database_host:
        credentials["host"] = settings.database_host
    if settings.database_port is not None:
        credentials["port"] = settings.database_port
    if settings.database_name:
        credentials["dbname"] = settings.database_name
    return psycopg.connect(settings.database_url, row_factory=dict_row, **credentials)
