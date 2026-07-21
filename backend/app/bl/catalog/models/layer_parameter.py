"""Provider parameter metadata exposed through the catalog."""

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class LayerParameter(BaseModel):
    name: str
    type: str
    display_name: str = ""
    description: str = ""
    required: bool = False
    single_value: bool = True
    options: List[str] = []
    is_dynamic: bool = False
    resolved_value: Optional[str] = None
    """Value chosen at layer-add time for a configurable Cubes parameter;
    None means the catalog workflow has not resolved it."""
    configured_value: Any = Field(default=None, exclude=True, repr=False)
    """Value configured by the provider metadata. It is kept out of model
    serialization because Cubes may mark configured parameters as passwords."""
