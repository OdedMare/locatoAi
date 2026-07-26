from typing import List

from pydantic import BaseModel, Field


class LayerFieldsResponse(BaseModel):
    layer_id: str
    fields: List[str] = Field(default_factory=list)
