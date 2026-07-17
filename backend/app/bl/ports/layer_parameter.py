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
    """Value chosen at layer-add time for a dynamic parameter (via the
    Cubes autocomplete route); None means it was never resolved."""
    configured_value: Any = Field(default=None, exclude=True, repr=False)
    """Value configured by the provider metadata. It is kept out of model
    serialization because Cubes may mark configured parameters as passwords."""
