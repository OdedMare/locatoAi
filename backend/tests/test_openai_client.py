from app.common.config import Settings
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.llm.openai_client import OpenAIJsonClient


def make_store(tmp_path, llm_base_url="https://llm.test/v1", openai_api_key="key-a"):
    env = Settings(
        _env_file=None,
        runtime_settings_file=str(tmp_path / "runtime-settings.json"),
        llm_base_url=llm_base_url,
        openai_api_key=openai_api_key,
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


def test_complete_json_reuses_client_across_calls(tmp_path, monkeypatch):
    """The two mandatory agent calls (select, build) plus any sample_field
    tool rounds must not each pay a fresh connection setup cost."""
    client = OpenAIJsonClient(make_store(tmp_path))

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

    class FakeCompletions:
        def create(self, **kwargs):
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
