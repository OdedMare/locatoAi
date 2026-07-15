from typing import Literal, Optional, Union

from pydantic import BaseModel


class SpatialRelationStep(BaseModel):
    """Base fields shared by topological relations against another layer."""

    id: str
    input: str
    target_layer: str
    target_field: Optional[str] = None
    target_operator: Optional[Literal["eq", "contains"]] = None
    target_value: Optional[Union[str, float]] = None
