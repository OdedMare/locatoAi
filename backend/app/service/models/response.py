"""Available LLM model identifiers."""

from typing import List

from pydantic import BaseModel


class ModelsResponse(BaseModel):
    models: List[str]
