"""Cached environment-settings provider."""

from functools import lru_cache


class SettingsProvider:
    @staticmethod
    @lru_cache
    def get():
        from app.common.config import Settings
        return Settings()
