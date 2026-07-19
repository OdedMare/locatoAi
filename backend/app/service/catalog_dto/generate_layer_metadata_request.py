from pydantic import Field

from app.service.catalog_dto.cubes_parameter_values import CubesParameterValues
from app.service.catalog_dto.cubes_query_mode import CubesQueryMode


class GenerateLayerMetadataRequest(CubesParameterValues):
    name: str = Field(min_length=1, max_length=200)
    provider: str = Field(default="mqs", min_length=1, max_length=50)
    source_url: str = Field(min_length=1, max_length=2000)
    cubes_query_mode: CubesQueryMode = "auto"
