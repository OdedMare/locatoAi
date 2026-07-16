from typing import Dict

from pydantic import BaseModel, Field

from app.service.catalog_dto.cubes_query_mode import CubesQueryMode


class GenerateLayerMetadataRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    provider: str = Field(default="mqs", min_length=1, max_length=50)
    source_url: str = Field(min_length=1, max_length=2000)
    cubes_query_mode: CubesQueryMode = "auto"
    cubes_dynamic_parameters: Dict[str, str] = Field(default_factory=dict, max_length=20)
