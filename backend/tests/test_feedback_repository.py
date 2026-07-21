from datetime import datetime, timezone

from app.common.config.settings import Settings
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.feedback_repository import PostgresFeedbackRepository


class FakeConnection:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def execute(self, query, params=None):
        self.calls.append((query, params))


def test_feedback_is_inserted_in_configured_postgres_table(tmp_path, monkeypatch):
    store = RuntimeSettingsStore(
        Settings(_env_file=None, runtime_settings_file=str(tmp_path / "settings.json"))
    )
    store.update({"feedback_table": "analytics.user_feedback"})
    connection = FakeConnection()
    monkeypatch.setattr(
        "app.dal.feedback_repository.connect", lambda ignored_store: connection
    )
    timestamp = datetime(2026, 7, 14, tzinfo=timezone.utc)

    PostgresFeedbackRepository(store).add(
        query="schools", verdict="up", selected_layers=["education"],
        reasoning="matched", clarify=None, timestamp=timestamp,
    )

    assert len(connection.calls) == 2
    assert 'CREATE TABLE IF NOT EXISTS "analytics"."user_feedback"' in connection.calls[0][0]
    assert 'INSERT INTO "analytics"."user_feedback"' in connection.calls[1][0]
    assert connection.calls[1][1] == (
        "schools", "up", '["education"]', "matched", None, timestamp
    )
