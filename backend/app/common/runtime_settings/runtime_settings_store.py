import json
from dataclasses import asdict, fields
from pathlib import Path

from app.common.config.settings import Settings
from app.common.runtime_settings.normalizers import (
    normalize_cubes_base_url,
    normalize_database_url,
    normalize_llm_base_url,
    normalize_mqs_base_url,
    normalize_tyche_base_url,
    validate_layers_table,
)
from app.common.runtime_settings.runtime_settings import RuntimeSettings

# Fields where None/empty means "clear the value", not "keep current".
_NULLABLE = (
    "database_port", "llm_base_url", "mqs_base_url", "mqs_user_id",
    "cubes_base_url", "tyche_base_url", "tyche_username",
)


class RuntimeSettingsStore:
    def __init__(self, env: Settings):
        self._path = Path(env.runtime_settings_file)
        self._settings = RuntimeSettings(
            llm_model=env.llm_model,
            llm_diet_mode=env.llm_diet_mode,
            llm_base_url=env.llm_base_url,
            openai_api_key=env.openai_api_key,
            mqs_base_url=env.mqs_base_url,
            mqs_user_id=env.mqs_user_id,
            mqs_verify_tls=env.mqs_verify_tls,
            cubes_base_url=env.cubes_base_url,
            cubes_token=env.cubes_token,
            cubes_verify_tls=env.cubes_verify_tls,
            tyche_base_url=env.tyche_base_url,
            tyche_username=env.tyche_username,
            tyche_token=env.tyche_token,
            tyche_verify_tls=env.tyche_verify_tls,
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

    def _apply(self, patch: dict, strict: bool) -> None:
        known = {f.name for f in fields(RuntimeSettings)}
        for key, value in patch.items():
            if key not in known:
                continue
            if key in _NULLABLE and (value is None or value == ""):
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
                elif key == "tyche_base_url":
                    value = normalize_tyche_base_url(value)
            except ValueError:
                if strict:
                    raise
                continue  # startup: skip the bad saved value, keep the default
            setattr(self._settings, key, value)
