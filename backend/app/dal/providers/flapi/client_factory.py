"""Validate the FLAPI credentials flunks needs."""

from app.common.errors.provider_error import ProviderError
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore


class FlapiClientFactory:
    """Resolves and validates FLAPI settings for flunks.

    flunks builds its own HTTP client from ``FlapiConfig``, so this holds no
    client of its own. It reads the store on every call, which is what keeps the
    Settings UI a live override with no restart.
    """

    def __init__(self, settings_store: RuntimeSettingsStore) -> None:
        self._store = settings_store

    def require_settings(self, require_username: bool = False):
        settings = self._store.get()
        if not settings.cubes_base_url:
            raise ProviderError("FLAPI base URL is not configured — set cubes_base_url")
        if not settings.cubes_token:
            raise ProviderError(
                "FLAPI authorization token is not configured — set cubes_token"
            )
        if require_username and not settings.flapi_username:
            raise ProviderError(
                "FLAPI username is not configured — set flapi_username"
            )
        return settings
