from typing import List

from pydantic import BaseModel, Field


class UpdateLayerRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    tags: List[str] = Field(default_factory=list, max_length=40)
