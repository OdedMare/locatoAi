import pytest
from openai import APIConnectionError, RateLimitError

from app.common.config import Settings
from app.common.errors.agent_error import AgentError
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.llm.openai_client import OpenAIJsonClient


def make_store(
    tmp_path, llm_base_url="https://llm.test/v1", openai_api_key="key-a",
    **overrides,
):
    env = Settings(
        _env_file=None,
        runtime_settings_file=str(tmp_path / "runtime-settings.json"),
        llm_base_url=llm_base_url,
        openai_api_key=openai_api_key,
        **overrides,
    )
    return RuntimeSettingsStore(env)


def test_client_for_reuses_the_same_instance_for_unchanged_settings(tmp_path):
    client = OpenAIJsonClient(make_store(tmp_path))
    first = client._client_for("key-a", "https://llm.test/v1")
    second = client._client_for("key-a", "https://llm.test/v1")
    assert first is second


def test_client_for_rebuilds_when_api_key_changes(tmp_path):
    client = OpenAIJsonClient(make_store(tmp_path))
    first = client._client_for("key-a", "https://llm.test/v1")
    second = client._client_for("key-b", "https://llm.test/v1")
    assert first is not second


def test_client_for_rebuilds_when_base_url_changes(tmp_path):
    client = OpenAIJsonClient(make_store(tmp_path))
    first = client._client_for("key-a", "https://llm.test/v1")
    second = client._client_for("key-a", "https://other.test/v1")
    assert first is not second


def test_retries_transient_connection_error_then_succeeds(tmp_path, monkeypatch):
    import httpx

    class FakeUsage:
        prompt_tokens = 1
        completion_tokens = 1
        total_tokens = 2

    class FakeMessage:
        content = '{"ok": true}'

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]
        usage = FakeUsage()

    calls = []

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise APIConnectionError(request=httpx.Request("POST", "https://llm.test"))
            return FakeResponse()

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = FakeChat()

    monkeypatch.setattr("app.dal.llm.openai_client.OpenAI", FakeOpenAI)
    monkeypatch.setattr("app.dal.llm.openai_client.time.sleep", lambda _seconds: None)

    client = OpenAIJsonClient(make_store(tmp_path))
    data = client.complete_json(system="s", user="u")
    assert data["ok"] is True
    assert len(calls) == 2  # one failure, one successful retry


def test_gives_up_after_max_transient_attempts(tmp_path, monkeypatch):
    import httpx

    calls = []

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            raise RateLimitError(
                "rate limited", response=httpx.Response(429, request=httpx.Request("POST", "https://llm.test")),
                body=None,
            )

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = FakeChat()

    monkeypatch.setattr("app.dal.llm.openai_client.OpenAI", FakeOpenAI)
    monkeypatch.setattr("app.dal.llm.openai_client.time.sleep", lambda _seconds: None)

    client = OpenAIJsonClient(make_store(tmp_path))
    with pytest.raises(AgentError, match="LLM request failed"):
        client.complete_json(system="s", user="u")
    # 2 transient attempts per degradation-ladder shape (only the first
    # shape is tried since the retry helper raises out of the ladder loop
    # entirely as a generic Exception, matching existing ladder behavior).
    assert len(calls) == 2


def test_complete_json_reuses_client_across_calls(tmp_path, monkeypatch):
    """The two mandatory agent calls (select, build) plus any sample_field
    tool rounds must not each pay a fresh connection setup cost."""
    store = make_store(tmp_path)
    client = OpenAIJsonClient(store)

    class FakeUsage:
        prompt_tokens = 1
        completion_tokens = 1
        total_tokens = 2

    class FakeMessage:
        content = '{"ok": true}'

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]
        usage = FakeUsage()

    calls = []

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            return FakeResponse()

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = FakeChat()

    monkeypatch.setattr("app.dal.llm.openai_client.OpenAI", FakeOpenAI)

    client.complete_json(system="s", user="u")
    first_client = client._cached_client
    client.complete_json(system="s2", user="u2")
    assert client._cached_client is first_client
    assert all(call["max_tokens"] == 1200 for call in calls)

    store.update({"llm_diet_mode": False})
    client.complete_json(system="full", user="u3")
    assert "max_tokens" not in calls[-1]
