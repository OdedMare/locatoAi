"""Top-level FLAPI provider dispatching Cube and Flow Package resources."""

from app.dal.providers.flapi.client_factory import FlapiClientFactory
from app.dal.providers.flapi.cube_provider import CubesProvider
from app.dal.providers.flapi.package_provider import FlowPackageProvider
from app.dal.providers.flapi.source import FlapiSource


class FlapiProvider:
    def __init__(self, settings_store, transport=None) -> None:
        self._source = FlapiSource()
        clients = FlapiClientFactory(settings_store, transport)
        self._cube = CubesProvider(clients)
        self._package = FlowPackageProvider(clients)

    def describe_schema(self, layer):
        return self._provider(layer).describe_schema(layer)

    def fetch_features(self, layer, **kwargs):
        return self._provider(layer).fetch_features(layer, **kwargs)

    def sample_for_metadata(self, layer, **kwargs):
        return self._provider(layer).sample_for_metadata(layer, **kwargs)

    def sample_field_values(self, layer, field, limit=20):
        return self._provider(layer).sample_field_values(layer, field, limit)

    def list_configurable_parameters(self, layer, refresh=False):
        return self._provider(layer).list_configurable_parameters(layer, refresh)

    def requires_geometry(self, layer):
        return self._provider(layer).requires_geometry(layer)

    def fetch_autocomplete_options(self, layer, parameter_name):
        return self._provider(layer).fetch_autocomplete_options(
            layer, parameter_name
        )

    def _provider(self, layer):
        return (
            self._package
            if self._source.resource_type(layer) == "package"
            else self._cube
        )
