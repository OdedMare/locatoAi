from typing import List

from pydantic import BaseModel


class SelectedLayerDto(BaseModel):
    """Agent trace: one layer the model chose (for the UI's agent panel)."""

    id: str
    name: str
    tags: List[str] = []
    description: str = ""
