"""Provider registry: catalog `provider` name → adapter instance.

OCP: registering a new provider is one `register` call in main.py.
"""

from typing import Dict

from app.bl.ports import Provider
from app.common.errors import ProviderError


class InMemoryProviderRegistry:
    def __init__(self) -> None:
        self._providers: Dict[str, Provider] = {}

    def register(self, name: str, provider: Provider) -> None:
        self._providers[name] = provider

    def get(self, provider_name: str) -> Provider:
        provider = self._providers.get(provider_name)
        if provider is None:
            raise ProviderError(f"No provider registered for '{provider_name}'")
        return provider
