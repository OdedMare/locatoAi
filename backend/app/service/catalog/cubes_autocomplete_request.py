"""Cubes autocomplete request."""

from pydantic import BaseModel, Field


class CubesAutocompleteRequest(BaseModel):
    source_url: str = Field(min_length=1, max_length=2000)
    parameter_name: str = Field(min_length=1, max_length=200)
