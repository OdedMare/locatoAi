from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TemporalFilterStep(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    op: Literal["temporal_filter"]
    input: str
    from_: str = Field(alias="from")  # ISO 8601
    to: str  # ISO 8601
