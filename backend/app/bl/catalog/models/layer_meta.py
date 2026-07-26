"""Business metadata for one catalog layer."""

from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class LayerMeta(BaseModel):
    """One row of the catalog (public.layers). Metadata only — never features."""

    id: str
    name: str
    description: str = ""
    tags: List[str] = Field(default_factory=list)
    provider: str
    source_url: str
    entity_field: Optional[str] = None
    display_field: Optional[str] = None
    profiles: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def decode_legacy_semantics(self):
        """Keep old tag-backed catalogs readable while the core stays typed."""
        tags, profiles = [], list(self.profiles)
        for tag in self.tags:
            name, separator, value = tag.partition(":")
            value = value.strip()
            if separator and name == "entity_field" and value:
                self.entity_field = self.entity_field or value
            elif separator and name == "display_field" and value:
                self.display_field = self.display_field or value
            elif separator and name == "profile" and value:
                profiles.append(value)
            else:
                tags.append(tag)
        self.tags = list(dict.fromkeys(tags))
        self.profiles = list(dict.fromkeys(
            profile.strip() for profile in profiles if profile.strip()
        ))
        return self

    def persisted_tags(self) -> List[str]:
        """Encode typed semantics only at the legacy Postgres boundary."""
        semantic = [
            *(["entity_field:" + self.entity_field] if self.entity_field else []),
            *(["display_field:" + self.display_field] if self.display_field else []),
            *["profile:" + profile for profile in self.profiles],
        ]
        return list(dict.fromkeys([*semantic, *self.tags]))
