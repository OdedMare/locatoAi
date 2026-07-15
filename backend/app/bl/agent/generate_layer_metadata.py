"""Generate editable catalog metadata from a small random entity sample."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from app.bl.ports.layer_meta import LayerMeta
from app.bl.ports.llm_client import LLMClient
from app.bl.ports.provider_registry import ProviderRegistry
from app.common.errors.agent_error import AgentError
from app.common.errors.provider_error import ProviderError

_PROMPT_PATH = Path(__file__).parent / "prompts" / "generate_layer_metadata.md"
_FETCH_LIMIT = 100
"""Cap on how many entities are fetched from the provider to classify a
layer — tagging needs a representative sample, not the whole layer
(a large MQS layer would otherwise cost a full paginated fetch just to
draw 10 rows out of it)."""
_SAMPLE_SIZE = 10
_MAX_FIELDS = 20
_MAX_VALUE_CHARS = 200
_MAX_TAGS = 20
_MAX_TAG_CHARS = 60
_MAX_DESCRIPTION_CHARS = 2000


@dataclass
class GeneratedLayerMetadata:
    description: str
    tags: List[str] = field(default_factory=list)
    sample_count: int = 0


class LayerMetadataGenerator:
    """Provider sample → bounded prompt → user-editable metadata suggestion."""

    def __init__(self, llm: LLMClient, providers: ProviderRegistry):
        self._llm = llm
        self._providers = providers
        self._prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    def generate(self, name: str, provider_name: str, source_url: str) -> GeneratedLayerMetadata:
        layer = LayerMeta(
            id="metadata-preview",
            name=name.strip(),
            provider=provider_name.strip(),
            source_url=source_url.strip(),
        )
        provider = self._providers.get(layer.provider)
        try:
            features = provider.fetch_features(layer, limit=_FETCH_LIMIT)
            schema = provider.describe_schema(layer)
        except Exception as exc:
            if isinstance(exc, ProviderError):
                raise
            raise ProviderError(
                "Could not sample the layer before generating metadata"
            ) from exc

        if features.empty:
            raise ProviderError("The layer has no entities to sample")

        sample_count = min(_SAMPLE_SIZE, len(features))
        sampled = features.sample(n=sample_count)
        records = []
        for raw_record in sampled.drop(columns=["geometry"], errors="ignore").to_dict("records"):
            record = {}
            for key, value in list(raw_record.items())[:_MAX_FIELDS]:
                record[str(key)[:_MAX_TAG_CHARS]] = str(value)[:_MAX_VALUE_CHARS]
            records.append(record)

        user = json.dumps(
            {
                "layer_name": layer.name,
                "source_name": schema.source_name,
                "source_description": schema.source_description,
                "geometry_type": schema.geometry_type,
                "fields": [
                    {"name": item.name, "type": item.type,
                     "description": item.description}
                    for item in schema.fields[:_MAX_FIELDS]
                ],
                "parameters": [item.model_dump() for item in schema.parameters[:_MAX_FIELDS]],
                "random_entity_sample": records,
            },
            ensure_ascii=False,
        )
        data = self._llm.complete_json(system=self._prompt, user=user)
        description = data.get("description")
        raw_tags = data.get("tags")
        if not isinstance(description, str) or not description.strip():
            raise AgentError("LLM metadata response has no description")
        if not isinstance(raw_tags, list):
            raise AgentError("LLM metadata response has no tags list")

        tags = []
        seen = set()
        for raw_tag in raw_tags:
            if not isinstance(raw_tag, str):
                continue
            tag = raw_tag.strip()[:_MAX_TAG_CHARS]
            key = tag.casefold()
            if tag and key not in seen:
                tags.append(tag)
                seen.add(key)
            if len(tags) >= _MAX_TAGS:
                break
        if not tags:
            raise AgentError("LLM metadata response contains no usable tags")

        return GeneratedLayerMetadata(
            description=description.strip()[:_MAX_DESCRIPTION_CHARS],
            tags=tags,
            sample_count=sample_count,
        )
