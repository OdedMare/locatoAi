"""Generate editable catalog metadata from a bounded provider sample."""

from pathlib import Path
from typing import List

from app.bl.agent.generate_layer_metadata.generated_layer_metadata import GeneratedLayerMetadata
from app.bl.agent.generate_layer_metadata.metadata_response_mapper import MetadataResponseMapper
from app.bl.agent.generate_layer_metadata.metadata_sample_builder import MetadataSampleBuilder
from app.bl.catalog.models.layer_meta import LayerMeta
from app.bl.catalog.models.layer_parameter import LayerParameter
from app.bl.agent.llm_client import LLMClient
from app.bl.providers.registry import ProviderRegistry
from app.common.errors.provider_error import ProviderError

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "generate_layer_metadata.md"


class LayerMetadataGenerator:
    _FETCH_LIMIT = 100

    def __init__(
        self, llm: LLMClient, providers: ProviderRegistry,
        content_repository=None,
    ) -> None:
        self._llm = llm
        self._providers = providers
        self._content_repository = content_repository
        self._sample_builder = MetadataSampleBuilder()
        self._response_mapper = MetadataResponseMapper()

    def generate(
        self, name: str, provider_name: str, source_url: str,
        sample_geometry=None,
    ) -> GeneratedLayerMetadata:
        layer = self._layer(name, provider_name, source_url)
        provider = self._providers.get(layer.provider)
        parameters = self._configurable_parameters(layer, provider)
        requires_polygon = self._requires_sample_polygon(layer, provider)
        if (
            any(
                item.required
                and item.resolved_value is None
                and item.configured_value in (None, "", [], {})
                for item in parameters
            )
            or (requires_polygon and sample_geometry is None)
        ):
            return self._unresolved(parameters, requires_polygon)
        features, schema = self._sample(
            layer, provider, sample_geometry
        )
        user, sample_count = self._sample_builder.build(layer, features, schema)
        data = self._llm.complete_json(system=self._prompt(), user=user)
        return self._response_mapper.map(
            data, sample_count, parameters, requires_polygon
        )

    def _prompt(self) -> str:
        if self._content_repository is not None:
            return self._content_repository.prompt("generate_layer_metadata.md")
        return _PROMPT_PATH.read_text(encoding="utf-8")

    def _sample(self, layer, provider, sample_geometry=None):
        try:
            metadata_sampler = getattr(provider, "sample_for_metadata", None)
            if callable(metadata_sampler):
                if layer.provider in ("cubes", "flapi"):
                    features, schema = metadata_sampler(
                        layer, limit=self._FETCH_LIMIT,
                        geometry=sample_geometry,
                    )
                else:
                    features, schema = metadata_sampler(
                        layer, limit=self._FETCH_LIMIT
                    )
            else:
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
        loader = getattr(provider, "list_configurable_parameters", None)
        if not callable(loader):
            return []
        # Catalog metadata is editable upstream. A fresh generation attempt
        # must see newly-required parameters instead of an old process-local
        # Cubes metadata cache entry.
        return loader(layer, refresh=True)

    @staticmethod
    def _requires_sample_polygon(layer: LayerMeta, provider) -> bool:
        checker = getattr(provider, "requires_geometry", None)
        return callable(checker) and checker(layer)

    @staticmethod
    def _unresolved(
        parameters, requires_sample_polygon: bool = False
    ) -> GeneratedLayerMetadata:
        return GeneratedLayerMetadata(
            description="", sample_count=0,
            dynamic_parameters=[item.name for item in parameters if item.is_dynamic],
            configurable_parameters=parameters,
            requires_sample_polygon=requires_sample_polygon,
        )
