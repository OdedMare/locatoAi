"""Cubes parameter response."""

from typing import List

from pydantic import BaseModel


class CubesParameterResponse(BaseModel):
    name: str
    display_name: str = ""
    required: bool = True
    dynamic: bool = False
    options: List[str] = []
