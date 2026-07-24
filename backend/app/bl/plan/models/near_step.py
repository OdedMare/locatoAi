from typing import Literal, Optional, Union

from pydantic import BaseModel, Field


class NearStep(BaseModel):
    id: str
    op: Literal["near"]
    input: str
    target_layer: str
    distance_m: float = Field(default=300, gt=0, le=5000)
    # A named landmark (for example "Venice Beach") narrows the reference
    # layer before distance calculation. All three fields are emitted together.
    target_field: Optional[str] = None
    target_operator: Optional[Literal["eq", "contains"]] = None
    target_value: Optional[Union[str, float]] = None
