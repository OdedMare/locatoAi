from typing import Literal

from pydantic import BaseModel, Field


class DirectionalStep(BaseModel):
    id: str
    op: Literal["directional"]
    input: str
    direction: Literal["north", "south", "east", "west"]
    count: int = Field(default=1, ge=1)
