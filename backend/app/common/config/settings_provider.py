"""Cached environment-settings provider."""

from functools import lru_cache

from app.common.config.settings import Settings


class SettingsProvider:
    @staticmethod
    @lru_cache
    def get() -> Settings:
        return Settings()


get_settings = SettingsProvider.get
