"""Selected layer included in a query response."""

from typing import List, Optional

from pydantic import BaseModel, Field


class SelectedLayerDto(BaseModel):
    """Agent trace: one layer the model chose (for the UI's agent panel)."""

    id: str
    name: str
    tags: List[str] = Field(default_factory=list)
    description: str = ""
    entity_field: Optional[str] = None
    display_field: Optional[str] = None
    profiles: List[str] = Field(default_factory=list)
