"""Application configuration (env-driven)."""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Env-derived DEFAULTS. Values the user can edit in the UI live in
    common.runtime_settings (this feeds its initial values)."""

    model_config = SettingsConfigDict(
        env_prefix="AILOCATOR_", env_file=".env", extra="ignore"
    )

    database_url: str = "postgresql://localhost:5432/gis"
    """Postgres holding the layer catalog."""

    database_user: str = ""
    """Optional explicit Postgres user. Overrides credentials in the URL."""

    database_password: str = ""
    """Optional explicit Postgres password. Never returned by the API."""

    database_host: str = ""
    """Optional explicit Postgres host. Overrides the host in the URL."""

    database_port: Optional[int] = None
    """Optional explicit Postgres port. Overrides the port in the URL."""

    database_name: str = ""
    """Optional explicit database name. Overrides the database in the URL."""

    layers_table: str = "public.layers"
    """Table with the layer metadata the agent chooses from."""

    llm_model: str = "gemma4:31b-cloud"
    """The main model — Gemma 4 31B served through Ollama."""

    llm_base_url: Optional[str] = "http://localhost:11434/v1"
    """OpenAI-compatible endpoint. Default: local Ollama. From inside the
    backend container use http://pghost:11434/v1 (see runtime-settings)."""

    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")

    runtime_settings_file: str = "runtime-settings.json"
    """UI-edited settings are persisted here, overriding the env defaults."""

    schema_cache_ttl_seconds: int = 3600
    """Provider schemas are cached this long; a stale schema beats a failed request."""

    data_dir: str = "data"
    """Directory of mock GeoJSON files served by the mock ArcGIS provider."""

    request_log_path: str = "logs/requests.jsonl"

    feedback_log_path: str = "logs/feedback.jsonl"
    """UI 👍/👎 verdicts land here — the raw material for new eval cases."""


@lru_cache
def get_settings() -> Settings:
    return Settings()
