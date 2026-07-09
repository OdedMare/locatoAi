"""Application configuration (env-driven)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AILOCATOR_", env_file=".env")

    database_url: str = "postgresql://localhost:5432/gis"
    """Postgres holding the layer catalog (public.layers)."""

    schema_cache_ttl_seconds: int = 3600
    """Provider schemas are cached this long; a stale schema beats a failed request."""

    data_dir: str = "data"
    """Directory of mock GeoJSON files served by the mock ArcGIS provider."""

    request_log_path: str = "logs/requests.jsonl"


@lru_cache
def get_settings() -> Settings:
    return Settings()
