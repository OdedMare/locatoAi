from typing import Literal, Optional, Union

from pydantic import BaseModel


class ProximityTarget(BaseModel):
    """One required reference in a multi-reference proximity query."""

    layer: str
    field: Optional[str] = None
    operator: Optional[Literal["eq", "contains"]] = None
    value: Optional[Union[str, float]] = None
