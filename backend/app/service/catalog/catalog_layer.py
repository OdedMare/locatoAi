"""Catalog layer response."""

from typing import List, Optional

from pydantic import BaseModel, Field


class CatalogLayer(BaseModel):
    id: str
    name: str
    description: str
    tags: List[str] = Field(default_factory=list)
    entity_field: Optional[str] = None
    display_field: Optional[str] = None
    profiles: List[str] = Field(default_factory=list)
