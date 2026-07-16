from typing import List, Optional

from pydantic import BaseModel


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
