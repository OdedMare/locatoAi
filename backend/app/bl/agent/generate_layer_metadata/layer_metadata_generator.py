"""Generate editable catalog metadata from a bounded provider sample."""

from pathlib import Path
from typing import List

from app.bl.agent.generate_layer_metadata.generated_layer_metadata import GeneratedLayerMetadata
from app.bl.agent.generate_layer_metadata.metadata_response_mapper import MetadataResponseMapper
from app.bl.agent.generate_layer_metadata.metadata_sample_builder import MetadataSampleBuilder
from app.bl.ports.layer_meta import LayerMeta
from app.bl.ports.layer_parameter import LayerParameter
from app.bl.ports.llm_client import LLMClient
from app.bl.ports.provider_registry import ProviderRegistry
from app.common.errors.provider_error import ProviderError

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "generate_layer_metadata.md"


class LayerMetadataGenerator:
    _FETCH_LIMIT = 100

    def __init__(self, llm: LLMClient, providers: ProviderRegistry) -> None:
        self._llm = llm
        self._providers = providers
        self._prompt = _PROMPT_PATH.read_text(encoding="utf-8")
        self._sample_builder = MetadataSampleBuilder()
        self._response_mapper = MetadataResponseMapper()

    def generate(
        self, name: str, provider_name: str, source_url: str
    ) -> GeneratedLayerMetadata:
        layer = self._layer(name, provider_name, source_url)
        provider = self._providers.get(layer.provider)
        parameters = self._configurable_parameters(layer, provider)
        if any(item.resolved_value is None for item in parameters):
            return self._unresolved(parameters)
        features, schema = self._sample(layer, provider)
        user, sample_count = self._sample_builder.build(layer, features, schema)
        data = self._llm.complete_json(system=self._prompt, user=user)
        return self._response_mapper.map(data, sample_count, parameters)

    def _sample(self, layer, provider):
        try:
            features = provider.fetch_features(layer, limit=self._FETCH_LIMIT)
            schema = provider.describe_schema(layer)
        except Exception as exc:
            if isinstance(exc, ProviderError):
                raise
            raise ProviderError(
                "Could not sample the layer before generating metadata"
            ) from exc
        if features.empty:
            raise ProviderError("The layer has no entities to sample")
        return features, schema

    @staticmethod
    def _layer(name, provider_name, source_url) -> LayerMeta:
        return LayerMeta(
            id="metadata-preview", name=name.strip(),
            provider=provider_name.strip(), source_url=source_url.strip(),
        )

    @staticmethod
    def _configurable_parameters(
        layer: LayerMeta, provider
    ) -> List[LayerParameter]:
        if layer.provider != "cubes":
            return []
        return provider.list_configurable_parameters(layer)

    @staticmethod
    def _unresolved(parameters) -> GeneratedLayerMetadata:
        return GeneratedLayerMetadata(
            description="", sample_count=0,
            dynamic_parameters=[item.name for item in parameters if item.is_dynamic],
            configurable_parameters=parameters,
        )
