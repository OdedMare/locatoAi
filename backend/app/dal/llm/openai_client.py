"""OpenAI-compatible JSON-mode LLM client.

Implements the bl.ports.LLMClient protocol. Model, API key, and base URL
come from the runtime settings store on EVERY call, so changes saved in
the UI settings panel apply immediately.

Robustness (ported policy from the MVP guide):
- asks for JSON mode when the server supports it, falls back if not
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


class OpenAIJsonClient:
    def __init__(self, settings_store: RuntimeSettingsStore):
        self._store = settings_store

    def complete_json(self, system: str, user: str) -> dict:
        settings = self._store.get()
        if not settings.openai_api_key:
            raise AgentError(
                "No API key configured — open Settings and add your OpenAI API key"
            )
        client = OpenAI(
            api_key=settings.openai_api_key,
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
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
                response_format={"type": "json_object"},
            )
        except BadRequestError:
            # Some OpenAI-compatible servers reject response_format.
            try:
                response = client.chat.completions.create(
                    model=model, messages=messages, temperature=0
                )
            except Exception as exc:
                raise AgentError("LLM request failed: " + str(exc))
        except Exception as exc:
            raise AgentError("LLM request failed: " + str(exc))
        content = response.choices[0].message.content
        if not content:
            raise AgentError("LLM returned an empty reply")
        return content
