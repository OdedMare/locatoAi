"""Create authenticated FLAPI HTTP clients."""

from typing import Optional

import httpx

from app.common.errors.provider_error import ProviderError
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore


class FlapiClientFactory:
    def __init__(
        self,
        settings_store: RuntimeSettingsStore,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self._store = settings_store
        self._transport = transport

    @property
    def transport(self) -> Optional[httpx.BaseTransport]:
        return self._transport

    def set_transport(self, transport: Optional[httpx.BaseTransport]) -> None:
        self._transport = transport

    def create(self, require_username: bool = False) -> httpx.Client:
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
        return httpx.Client(
            base_url=settings.cubes_base_url,
            headers=self._headers(
                settings.cubes_token, settings.flapi_username
            ),
            timeout=None,  # explicit: omitting it would apply httpx's 5s default
            verify=settings.cubes_verify_tls,
            transport=self._transport,
        )

    @staticmethod
    def _headers(token: str, username: Optional[str] = None) -> dict:
        authorization = token.strip()
        if not authorization.casefold().startswith("bearer "):
            authorization = f"Bearer {authorization}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": authorization,
        }
        if username:
            headers["username"] = username
        return headers
