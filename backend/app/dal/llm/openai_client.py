"""OpenAI-compatible JSON-mode LLM client.

Implements the bl.ports.LLMClient protocol. Model, API key, and base URL
come from the runtime settings store on EVERY call, so changes saved in
the UI settings panel apply immediately. Works against OpenAI itself and
OpenAI-compatible servers (Ollama, vLLM, Groq...) — the main model is
Gemma 4 31B served through Ollama.

Robustness (ported policy from the MVP guide):
- no API key required when a custom base_url is set (local servers)
- asks for JSON mode when the server supports it, falls back if not
- merges the system prompt into the user turn for servers/models that
  reject a system role (some Gemma deployments)
- strips markdown fences from the reply
- retries once with the parse error appended before giving up
"""

import json
import re

from openai import BadRequestError, OpenAI

from app.common.errors import AgentError
from app.common.runtime_settings import RuntimeSettingsStore


def extract_json(text: str) -> dict:
    """Parse a JSON object out of an LLM reply (tolerates ``` fences and prose)."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[A-Za-z]*\s*", "", cleaned)
        cleaned = re.sub(r"```\s*$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


def _merge_system_into_user(messages: list) -> list:
    """Fold system content into the first user message, keep other turns."""
    system_parts = [m["content"] for m in messages if m["role"] == "system"]
    rest = [m for m in messages if m["role"] != "system"]
    if not system_parts or not rest:
        return rest or messages
    merged = dict(rest[0])
    merged["content"] = "\n\n".join(system_parts + [merged["content"]])
    return [merged] + rest[1:]


class OpenAIJsonClient:
    def __init__(self, settings_store: RuntimeSettingsStore):
        self._store = settings_store

    def complete_json(self, system: str, user: str) -> dict:
        settings = self._store.get()
        if not settings.openai_api_key and not settings.llm_base_url:
            raise AgentError(
                "No API key configured — open Settings and add an API key, "
                "or set a base URL for a local server (e.g. Ollama)"
            )
        client = OpenAI(
            # SDK requires a non-empty key; local servers ignore its value.
            api_key=settings.openai_api_key or "not-needed",
            base_url=settings.llm_base_url or None,
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        last_error = "unknown"
        for _attempt in range(2):
            content = self._complete(client, settings.llm_model, messages)
            try:
                return extract_json(content)
            except json.JSONDecodeError as exc:
                last_error = str(exc)
                messages = messages + [
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": (
                            "That was not valid JSON (" + last_error + "). "
                            "Reply again with ONLY the JSON object."
                        ),
                    },
                ]
        raise AgentError("LLM returned unparseable JSON twice: " + last_error)

    @staticmethod
    def _complete(client: "OpenAI", model: str, messages: list) -> str:
        # Degradation ladder for OpenAI-compatible servers:
        # 1. JSON mode → 2. plain → 3. plain with the system prompt merged
        # into the user turn (some Gemma deployments reject a system role).
        attempts = [
            {"messages": messages, "response_format": {"type": "json_object"}},
            {"messages": messages},
            {"messages": _merge_system_into_user(messages)},
        ]
        last_bad_request = None
        for kwargs in attempts:
            try:
                response = client.chat.completions.create(
                    model=model, temperature=0, **kwargs
                )
                break
            except BadRequestError as exc:
                last_bad_request = exc
            except Exception as exc:
                raise AgentError("LLM request failed: " + str(exc))
        else:
            raise AgentError("LLM request failed: " + str(last_bad_request))

        content = response.choices[0].message.content
        if not content:
            raise AgentError("LLM returned an empty reply")
        return content
