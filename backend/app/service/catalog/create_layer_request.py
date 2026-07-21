from typing import List

from pydantic import Field

from app.service.catalog.cubes_parameter_values import CubesParameterValues
from app.service.catalog.cubes_query_mode import CubesQueryMode


class CreateLayerRequest(CubesParameterValues):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    tags: List[str] = []
    provider: str = Field(default="mqs", min_length=1, max_length=50)
    source_url: str = Field(min_length=1, max_length=2000)
    cubes_query_mode: CubesQueryMode = "auto"
