"""Layer selected by the agent debug endpoint."""

from typing import List

from pydantic import BaseModel


class SelectedLayer(BaseModel):
    id: str
    name: str
    tags: List[str]
