"""Catalog layer metadata update request."""

from typing import List, Optional

from pydantic import BaseModel, Field


class UpdateLayerRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    tags: List[str] = Field(default_factory=list, max_length=40)
    entity_field: Optional[str] = Field(
        default=None, min_length=1, max_length=60
    )
    display_field: Optional[str] = Field(
        default=None, min_length=1, max_length=60
    )
    profiles: Optional[List[str]] = Field(default=None, max_length=10)
