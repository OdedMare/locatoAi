"""Cubes autocomplete option response."""

from pydantic import BaseModel


class CubesAutocompleteOptionResponse(BaseModel):
    value: str
    name: str
