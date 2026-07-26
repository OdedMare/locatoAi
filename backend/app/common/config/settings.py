"""Application configuration (env-driven)."""

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

    feedback_table: str = "public.feedback"
    """Table where UI thumbs-up/down feedback is stored."""

    llm_model: str = "gemma4:31b-cloud"
    """The main model — Gemma 4 31B served through Ollama."""

    llm_diet_mode: bool = True
    """Use compact prompts, schema samples, and bounded completion output."""

    llm_base_url: Optional[str] = "http://localhost:11434/v1"
    """OpenAI-compatible endpoint. Default: local Ollama. From inside the
    backend container use http://pghost:11434/v1 (see runtime-settings)."""

    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")

    mqs_base_url: Optional[str] = None
    """Base URL of the MQS (Moria Query Service) GIS server. Unset = the
    'mqs' provider is unavailable until configured in the settings panel."""

    mqs_user_id: Optional[str] = None
    """Sent as the required User_ID header on every MQS request (the
    official Entities doc's example value is "tt/T"). Deployment-specific;
    unset = header omitted."""

    mqs_verify_tls: bool = True

    mqs_detail_concurrency: int = 16
    """Maximum concurrent MQS detail requests for changed entities."""

    cubes_base_url: Optional[str] = None
    """Base URL hosting /cube/v1/<dbname>."""

    cubes_token: str = ""
    """Authorization header value for the Cubes API. Never returned by the API."""

    flapi_username: Optional[str] = None
    """Value of FLAPI's ``username`` header for Cubes and Flow Packages."""

    cubes_verify_tls: bool = True

    tyche_base_url: Optional[str] = None
    """Base URL hosting POST /coordinate/v1/ourforces."""

    tyche_username: Optional[str] = None
    """Value of Tyche's required ``username`` request header."""

    tyche_token: str = ""
    """Authorization header value for Tyche. Never returned by the API."""

    tyche_verify_tls: bool = True

    runtime_settings_file: str = "runtime-settings.json"
    """UI-edited settings are persisted here, overriding the env defaults."""

    schema_cache_ttl_seconds: int = 3600
    """Provider schemas are cached this long; a stale schema beats a failed request."""

    request_log_path: str = "logs/requests.jsonl"
