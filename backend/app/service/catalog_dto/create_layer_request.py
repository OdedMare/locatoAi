from typing import List

from pydantic import BaseModel, Field

from app.service.catalog_dto.cubes_query_mode import CubesQueryMode


class CreateLayerRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    tags: List[str] = []
    provider: str = Field(default="mqs", min_length=1, max_length=50)
    source_url: str = Field(min_length=1, max_length=2000)
    cubes_query_mode: CubesQueryMode = "auto"
