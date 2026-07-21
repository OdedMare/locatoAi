from typing import List

from pydantic import BaseModel

from app.service.catalog.cubes_autocomplete_option_response import (
    CubesAutocompleteOptionResponse,
)


class CubesAutocompleteResponse(BaseModel):
    options: List[CubesAutocompleteOptionResponse]
