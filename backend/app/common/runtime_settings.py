"""Runtime-editable settings (the ones exposed in the UI settings panel).

Env vars / .env provide the defaults (common.config); anything the user
saves in the UI is persisted to a JSON file and overrides them. Consumers
(repository, LLM client) read from the store on every use, so changes
apply immediately — no restart.
"""

import json
import re
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Optional

from app.common.config import Settings

# schema.table or bare table; identifiers only — this is interpolated into
# SQL, so it must never accept arbitrary strings.
_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")

_JDBC_PREFIX = re.compile(r"^jdbc:", re.IGNORECASE)
_PG_SCHEMES = ("postgresql://", "postgres://")


def normalize_llm_base_url(url: str) -> str:
    cleaned = url.strip().rstrip("/")
    for suffix in ("/chat/completions", "/completions", "/models"):
        if cleaned.lower().endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
            break
    if not cleaned.lower().startswith(("http://", "https://")):
        raise ValueError(
            "llm_base_url must start with http:// or https:// "
            "(e.g. https://my-server/openai/v1)"
        )
    return cleaned


def normalize_mqs_base_url(url: str) -> str:
    cleaned = url.strip().rstrip("/")
    for suffix in ("/services", "/moriaproject"):
        if cleaned.lower().endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
            break
    if not cleaned.lower().startswith(("http://", "https://")):
        raise ValueError(
            "mqs_base_url must start with http:// or https:// "
            "(e.g. https://mqs.example/api)"
        )
    return cleaned


def normalize_cubes_base_url(url: str) -> str:
    cleaned = url.strip().rstrip("/")
    suffix = "/cube/v1"
    if cleaned.lower().endswith(suffix):
        cleaned = cleaned[: -len(suffix)]
    if not cleaned.lower().startswith(("http://", "https://")):
        raise ValueError(
            "cubes_base_url must start with http:// or https:// "
            "(e.g. https://cubes.example/api)"
        )
    return cleaned.rstrip("/")


def normalize_database_url(url: str) -> str:
    cleaned = _JDBC_PREFIX.sub("", url.strip())
    if not cleaned.lower().startswith(_PG_SCHEMES):
        raise ValueError(
            "database_url must start with postgresql:// "
            "(jdbc:postgresql://... is accepted and converted automatically)"
        )
    return cleaned


@dataclass
class RuntimeSettings:
    llm_model: str
    llm_base_url: Optional[str]
    openai_api_key: str
    mqs_base_url: Optional[str]
    mqs_user_id: Optional[str]
    mqs_verify_tls: bool
    cubes_base_url: Optional[str]
    cubes_token: str
    cubes_verify_tls: bool
    database_url: str
    database_user: str
    database_password: str
    database_host: str
    database_port: Optional[int]
    database_name: str
    layers_table: str
    feedback_table: str

    def quoted_layers_table(self) -> str:
        """The layers table as a safely quoted SQL identifier."""
        parts = self.layers_table.split(".")
        return ".".join(f'"{part}"' for part in parts)

    def quoted_feedback_table(self) -> str:
        """The feedback table as a safely quoted SQL identifier."""
        parts = self.feedback_table.split(".")
        return ".".join(f'"{part}"' for part in parts)


def validate_layers_table(name: str) -> None:
    if not _TABLE_RE.match(name):
        raise ValueError(
            "layers_table must be a plain identifier like 'layers' or 'public.layers'"
        )


class RuntimeSettingsStore:
    def __init__(self, env: Settings):
        self._path = Path(env.runtime_settings_file)
        self._settings = RuntimeSettings(
            llm_model=env.llm_model,
            llm_base_url=env.llm_base_url,
            openai_api_key=env.openai_api_key,
            mqs_base_url=env.mqs_base_url,
            mqs_user_id=env.mqs_user_id,
            mqs_verify_tls=env.mqs_verify_tls,
            cubes_base_url=env.cubes_base_url,
            cubes_token=env.cubes_token,
            cubes_verify_tls=env.cubes_verify_tls,
            database_url=env.database_url,
            database_user=env.database_user,
            database_password=env.database_password,
            database_host=env.database_host,
            database_port=env.database_port,
            database_name=env.database_name,
            layers_table=env.layers_table,
            feedback_table=env.feedback_table,
        )
        if self._path.exists():
            saved = json.loads(self._path.read_text(encoding="utf-8"))
            # Lenient on startup: a bad saved value must not prevent boot.
            self._apply(saved, strict=False)

    def get(self) -> RuntimeSettings:
        return self._settings

    def update(self, patch: dict) -> RuntimeSettings:
        """Apply a partial update, validate, and persist."""
        self._apply(patch, strict=True)
        self._path.write_text(
            json.dumps(asdict(self._settings), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return self._settings

    # Fields where None/empty means "clear the value", not "keep current".
    _NULLABLE = (
        "database_port", "llm_base_url", "mqs_base_url", "mqs_user_id",
        "cubes_base_url",
    )

    def _apply(self, patch: dict, strict: bool) -> None:
        known = {f.name for f in fields(RuntimeSettings)}
        for key, value in patch.items():
            if key not in known:
                continue
            if key in self._NULLABLE and (value is None or value == ""):
                setattr(self._settings, key, None)
                continue
            if value is None:
                continue
            try:
                if key in ("layers_table", "feedback_table"):
                    validate_layers_table(value)
                elif key == "database_url":
                    value = normalize_database_url(value)
                elif key == "llm_base_url":
                    value = normalize_llm_base_url(value)
                elif key == "mqs_base_url":
                    value = normalize_mqs_base_url(value)
                elif key == "cubes_base_url":
                    value = normalize_cubes_base_url(value)
            except ValueError:
                if strict:
                    raise
                continue  # startup: skip the bad saved value, keep the default
            setattr(self._settings, key, value)
