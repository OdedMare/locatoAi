from typing import Literal, Optional, Union
from pydantic import BaseModel, Field


class NearestNStep(BaseModel):
    id: str
    op: Literal["nearest_n"]
    input: str
    target_layer: str
    count: int = Field(gt=0, le=50)
    target_field: Optional[str] = None
    target_operator: Optional[Literal["eq", "contains"]] = None
    target_value: Optional[Union[str, float]] = None
