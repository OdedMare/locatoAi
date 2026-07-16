from typing import Protocol

from app.bl.ports.provider import Provider


class ProviderRegistry(Protocol):
    """Resolves a catalog `provider` name to a Provider instance."""

    def get(self, provider_name: str) -> Provider: ...

    def has(self, provider_name: str) -> bool: ...
