"""Cached environment settings."""

from functools import lru_cache

from app.common.config.settings import Settings


@lru_cache
def get_settings() -> Settings:
    return Settings()
