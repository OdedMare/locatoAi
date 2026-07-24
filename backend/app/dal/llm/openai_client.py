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
import time  # compatibility seam for tests patching transient retry sleeps

import httpx
from openai import (
    BadRequestError,
    OpenAI,
)

from app.common.errors.agent_error import AgentError
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.llm.completion_retry import CompletionRetry
from app.dal.llm.json_response_parser import JsonResponseParser
from app.dal.llm.message_merger import MessageMerger
from app.dal.llm.model_id_extractor import ModelIdExtractor


# One initial attempt + one retry with the parse error appended.
_MAX_JSON_ATTEMPTS = 2
# Deterministic output — the agent emits structured JSON, not prose.
_TEMPERATURE = 0
_DIET_MAX_COMPLETION_TOKENS = 1200
# The SDK requires a non-empty key; local servers/gateways ignore it.
# "null" is the value spear_presenton uses against the same gateways.
_LOCAL_SERVER_KEY_PLACEHOLDER = "null"

# A momentary rate-limit/connection blip must not fail the whole
# select/build/tool-round pipeline outright. Short fixed delay, not
# exponential backoff — this sits in the interactive request path, so
# total added worst-case latency must stay well under a second.
extract_json = JsonResponseParser.parse
extract_model_ids = ModelIdExtractor.extract
_create_with_retry = CompletionRetry.create
_merge_system_into_user = MessageMerger.merge_system_into_user


class OpenAIJsonClient:
    def __init__(self, settings_store: RuntimeSettingsStore):
        self._store = settings_store
        self._cached_client = None
        self._cached_key = None

    def complete_json(self, system: str, user: str, schema=None) -> dict:
        settings = self._store.get()
        self._validate_configuration(settings)
        client = self._client_for(settings.openai_api_key, settings.llm_base_url)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        last_error = "unknown"
        total_usage = self._empty_usage()
        for _attempt in range(_MAX_JSON_ATTEMPTS):
            content, usage = self._complete_for_settings(
                client, settings, messages, schema
            )
            self._add_usage(total_usage, usage)
            try:
                return self._parse_with_usage(content, total_usage)
            except json.JSONDecodeError as exc:
                last_error = str(exc)
                messages = self._retry_messages(messages, content, last_error)
        raise AgentError("LLM returned unparseable JSON twice: " + last_error)

    def list_models(self, base_url_override=None, api_key_override=None):
        """Return model ids exposed by the configured compatible API.

        Overrides let the settings panel test values typed in the form
        BEFORE saving them. Fetches /models raw and tolerates the response
        shapes seen in the wild: OpenAI's {"data": [{"id": ...}]},
        gateways' {"models": [...]}, bare lists, and items keyed by
        id/name/model or plain strings.
        """
        effective_base, effective_key = self._model_credentials(
            base_url_override, api_key_override
        )
        if not effective_key and not effective_base:
            raise AgentError(
                "No API key configured — add an API key or a compatible base URL"
            )
        try:
            response = httpx.get(
                (effective_base or "https://api.openai.com/v1").rstrip("/") + "/models",
                headers=self._authorization(effective_key), timeout=30,
            )
            response.raise_for_status()
            return extract_model_ids(response.json())
        except Exception as exc:
            raise AgentError("Could not list LLM models: " + str(exc))

    def _client_for(self, api_key: str, base_url: str) -> "OpenAI":
        """Reuse one OpenAI client (and its underlying httpx connection
        pool) across calls — a fresh client per call paid a TCP/TLS
        handshake on every one of the pipeline's several LLM round-trips
        (select, build, up to 3 sample_field tool rounds, zero-result
        replan). Re-keyed automatically when settings change mid-session
        (RuntimeSettingsStore is read per call, not cached)."""
        cache_key = (api_key, base_url)
        if self._cached_client is None or self._cached_key != cache_key:
            self._cached_client = OpenAI(
                api_key=api_key or _LOCAL_SERVER_KEY_PLACEHOLDER,
                base_url=base_url or None,
            )
            self._cached_key = cache_key
        return self._cached_client

    def _complete_for_settings(self, client, settings, messages, schema=None):
        max_tokens = _DIET_MAX_COMPLETION_TOKENS if settings.llm_diet_mode else None
        return self._complete(
            client, settings.llm_model, messages,
            max_tokens=max_tokens, schema=schema,
        )

    @staticmethod
    def _validate_configuration(settings) -> None:
        if not settings.openai_api_key and not settings.llm_base_url:
            raise AgentError(
                "No API key configured — open Settings and add an API key, "
                "or set a base URL for a local server (e.g. Ollama)"
            )

    @staticmethod
    def _empty_usage() -> dict:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    @staticmethod
    def _add_usage(total: dict, usage: dict) -> None:
        for key in total:
            total[key] += usage.get(key, 0)

    @staticmethod
    def _parse_with_usage(content: str, usage: dict) -> dict:
        data = extract_json(content)
        if usage["total_tokens"] > 0:
            data["_usage"] = usage
        return data

    @staticmethod
    def _retry_messages(messages: list, content: str, error: str) -> list:
        return messages + [
            {"role": "assistant", "content": content},
            {"role": "user", "content": (
                "That was not valid JSON (" + error + "). "
                "Reply again with ONLY the JSON object."
            )},
        ]

    def _model_credentials(self, base_override, key_override):
        settings = self._store.get()
        return (
            base_override or settings.llm_base_url,
            key_override or settings.openai_api_key,
        )

    @staticmethod
    def _authorization(api_key) -> dict:
        return {"Authorization": "Bearer " + (
            api_key or _LOCAL_SERVER_KEY_PLACEHOLDER
        )}

    @staticmethod
    def _complete(
        client: "OpenAI", model: str, messages: list,
        max_tokens=None, schema=None,
    ):
        # Degradation ladder for OpenAI-compatible servers:
        # 1. JSON mode → 2. plain → 3. plain with the system prompt merged
        # into the user turn (some Gemma deployments reject a system role).
        attempts = OpenAIJsonClient._attempts(messages, max_tokens, schema)
        last_bad_request = None
        for kwargs in attempts:
            try:
                response = _create_with_retry(client, model, kwargs)
                break
            except BadRequestError as exc:
                last_bad_request = exc
            except Exception as exc:
                raise AgentError("LLM request failed: " + str(exc))
        else:
            raise AgentError("LLM request failed: " + str(last_bad_request))

        return OpenAIJsonClient._response_data(response)

    @staticmethod
    def _attempts(messages: list, max_tokens=None, schema=None) -> list:
        attempts = []
        if schema is not None:
            attempts.append({
                "messages": messages,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "geo_plan_response",
                        "schema": schema,
                    },
                },
            })
        attempts.extend([
            {"messages": messages, "response_format": {"type": "json_object"}},
            {"messages": messages},
            {"messages": _merge_system_into_user(messages)},
        ])
        if max_tokens is None:
            return attempts
        return [{**kwargs, "max_tokens": max_tokens} for kwargs in attempts]

    @staticmethod
    def _response_data(response):
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
