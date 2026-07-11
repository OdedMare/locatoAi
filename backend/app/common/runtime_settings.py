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


@dataclass
class RuntimeSettings:
    llm_model: str
    llm_base_url: Optional[str]
    openai_api_key: str
    database_url: str
    database_user: str
    database_password: str
    database_host: str
    database_port: Optional[int]
    database_name: str
    layers_table: str

    def quoted_layers_table(self) -> str:
        """The layers table as a safely quoted SQL identifier."""
        parts = self.layers_table.split(".")
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
            database_url=env.database_url,
            database_user=env.database_user,
            database_password=env.database_password,
            database_host=env.database_host,
            database_port=env.database_port,
            database_name=env.database_name,
            layers_table=env.layers_table,
        )
        if self._path.exists():
            saved = json.loads(self._path.read_text(encoding="utf-8"))
            self._apply(saved)

    def get(self) -> RuntimeSettings:
        return self._settings

    def update(self, patch: dict) -> RuntimeSettings:
        """Apply a partial update, validate, and persist."""
        self._apply(patch)
        self._path.write_text(
            json.dumps(asdict(self._settings), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return self._settings

    def _apply(self, patch: dict) -> None:
        known = {f.name for f in fields(RuntimeSettings)}
        for key, value in patch.items():
            if key not in known:
                continue
            if key == "database_port" and value is None:
                self._settings.database_port = None
                continue
            if value is None:
                continue
            if key == "layers_table":
                validate_layers_table(value)
            setattr(self._settings, key, value)
