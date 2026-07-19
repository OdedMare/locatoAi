"""Validate and bound LLM-generated catalog metadata."""

from app.bl.agent.generate_layer_metadata.generated_layer_metadata import GeneratedLayerMetadata
from app.common.errors.agent_error import AgentError


class MetadataResponseMapper:
    _MAX_TAGS = 20
    _MAX_TAG_CHARS = 60
    _MAX_DESCRIPTION_CHARS = 2000

    def map(self, data, sample_count, dynamic_parameters):
        description = data.get("description")
        raw_tags = data.get("tags")
        if not isinstance(description, str) or not description.strip():
            raise AgentError("LLM metadata response has no description")
        if not isinstance(raw_tags, list):
            raise AgentError("LLM metadata response has no tags list")
        tags = self._tags(raw_tags)
        if not tags:
            raise AgentError("LLM metadata response contains no usable tags")
        return GeneratedLayerMetadata(
            description=description.strip()[:self._MAX_DESCRIPTION_CHARS],
            tags=tags, sample_count=sample_count,
            dynamic_parameters=[
                item.name for item in dynamic_parameters if item.is_dynamic
            ],
            configurable_parameters=dynamic_parameters,
        )

    def _tags(self, raw_tags):
        tags, seen = [], set()
        for raw_tag in raw_tags:
            tag = raw_tag.strip()[:self._MAX_TAG_CHARS] if isinstance(raw_tag, str) else ""
            key = tag.casefold()
            if tag and key not in seen:
                tags.append(tag)
                seen.add(key)
            if len(tags) >= self._MAX_TAGS:
                break
        return tags
