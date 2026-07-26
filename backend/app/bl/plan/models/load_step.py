from typing import Literal

from pydantic import BaseModel


class LoadStep(BaseModel):
    id: str
    op: Literal["load"]
    layer: str
