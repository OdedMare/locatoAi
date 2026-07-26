from typing import Literal

from pydantic import BaseModel


class LatestPerEntityStep(BaseModel):
    id: str
    op: Literal["latest_per_entity"]
    input: str
    entity_field: str
    time_field: str
