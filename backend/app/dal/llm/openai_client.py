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

import httpx
from openai import BadRequestError, OpenAI

from app.common.errors import AgentError
from app.common.runtime_settings import RuntimeSettingsStore


# One initial attempt + one retry with the parse error appended.
_MAX_JSON_ATTEMPTS = 2
# Deterministic output — the agent emits structured JSON, not prose.
_TEMPERATURE = 0
# The SDK requires a non-empty key; local servers/gateways ignore it.
# "null" is the value spear_presenton uses against the same gateways.
_LOCAL_SERVER_KEY_PLACEHOLDER = "null"


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


def extract_model_ids(payload) -> list:
    """Model ids from any common /models response shape."""
    items = payload
    if isinstance(payload, dict):
        items = payload.get("data")
        if items is None:
            items = payload.get("models")
    if not isinstance(items, list):
        return []
    ids = set()
    for item in items:
        if isinstance(item, str):
            ids.add(item)
        elif isinstance(item, dict):
            model_id = item.get("id") or item.get("name") or item.get("model")
            if model_id:
                ids.add(str(model_id))
    return sorted(ids)


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
            api_key=settings.openai_api_key or _LOCAL_SERVER_KEY_PLACEHOLDER,
            base_url=settings.llm_base_url or None,
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        last_error = "unknown"
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        for _attempt in range(_MAX_JSON_ATTEMPTS):
            content, usage = self._complete(client, settings.llm_model, messages)
            for key in total_usage:
                total_usage[key] += usage.get(key, 0)
            try:
                data = extract_json(content)
                if total_usage["total_tokens"] > 0:
                    data["_usage"] = total_usage
                return data
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

    def list_models(self, base_url_override=None, api_key_override=None):
        """Return model ids exposed by the configured compatible API.

        Overrides let the settings panel test values typed in the form
        BEFORE saving them. Fetches /models raw and tolerates the response
        shapes seen in the wild: OpenAI's {"data": [{"id": ...}]},
        gateways' {"models": [...]}, bare lists, and items keyed by
        id/name/model or plain strings.
        """
        settings = self._store.get()
        effective_base = base_url_override or settings.llm_base_url
        effective_key = api_key_override or settings.openai_api_key
        if not effective_key and not effective_base:
            raise AgentError(
                "No API key configured — add an API key or a compatible base URL"
            )
        base_url = (effective_base or "https://api.openai.com/v1").rstrip("/")
        headers = {
            "Authorization": "Bearer "
            + (effective_key or _LOCAL_SERVER_KEY_PLACEHOLDER)
        }
        try:
            response = httpx.get(base_url + "/models", headers=headers, timeout=30)
            response.raise_for_status()
            return extract_model_ids(response.json())
        except Exception as exc:
            raise AgentError("Could not list LLM models: " + str(exc))

    @staticmethod
    def _complete(client: "OpenAI", model: str, messages: list):
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
                    model=model, temperature=_TEMPERATURE, **kwargs
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
        usage = response.usage
        token_usage = {
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
            "total_tokens": usage.total_tokens if usage else 0,
        }
        return content, token_usage
