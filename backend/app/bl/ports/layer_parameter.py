from typing import List

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
