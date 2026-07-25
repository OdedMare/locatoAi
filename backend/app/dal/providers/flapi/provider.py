"""Top-level FLAPI provider — Flow Packages only."""

from app.bl.providers.provider import TEMPORAL_PUSHDOWN
from app.dal.providers.flapi.client_factory import FlapiClientFactory
from app.dal.providers.flapi.package_provider import FlowPackageProvider


class FlapiProvider:
    capabilities = frozenset({TEMPORAL_PUSHDOWN})

    def __init__(self, settings_store) -> None:
        # No httpx transport seam: flunks owns the FLAPI HTTP conversation, so
        # package tests substitute the flunks runner instead of a transport.
        self._package = FlowPackageProvider(FlapiClientFactory(settings_store))

    def describe_schema(self, layer):
        return self._package.describe_schema(layer)

    def fetch_features(self, layer, **kwargs):
        return self._package.fetch_features(layer, **kwargs)

    def sample_for_metadata(self, layer, **kwargs):
        return self._package.sample_for_metadata(layer, **kwargs)

    def sample_field_values(self, layer, field, limit=20):
        return self._package.sample_field_values(layer, field, limit)
