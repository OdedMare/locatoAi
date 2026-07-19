from typing import List

from pydantic import BaseModel

from app.service.catalog_dto.cubes_parameter_response import CubesParameterResponse


class GeneratedLayerMetadataResponse(BaseModel):
    description: str
    tags: List[str]
    sample_count: int
    dynamic_parameters: List[str] = []
    configurable_parameters: List[CubesParameterResponse] = []
