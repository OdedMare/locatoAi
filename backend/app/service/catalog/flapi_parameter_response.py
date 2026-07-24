"""FLAPI resource parameter response."""

from typing import List

from pydantic import BaseModel


class FlapiParameterResponse(BaseModel):
    name: str
    display_name: str = ""
    description: str = ""
    type: str = "string"
    required: bool = True
    single_value: bool = True
    ontology_type: str = ""
    has_default: bool = False
    dynamic: bool = False
    options: List[str] = []
