from typing import Literal, Optional, Union

from pydantic import BaseModel, Field


class BetweenStep(BaseModel):
    id: str
    op: Literal["between"]
    input: str
    first_target_layer: str
    second_target_layer: str
    corridor_width_m: float = Field(default=100, gt=0, le=5000)
    first_target_field: Optional[str] = None
    first_target_operator: Optional[Literal["eq", "contains"]] = None
    first_target_value: Optional[Union[str, float]] = None
    second_target_field: Optional[str] = None
    second_target_operator: Optional[Literal["eq", "contains"]] = None
    second_target_value: Optional[Union[str, float]] = None
