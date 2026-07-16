from typing import List

from pydantic import BaseModel


class GeneratedLayerMetadataResponse(BaseModel):
    description: str
    tags: List[str]
    sample_count: int
    dynamic_parameters: List[str] = []
