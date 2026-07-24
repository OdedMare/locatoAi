from typing import List

from pydantic import BaseModel

from app.service.catalog.flapi_parameter_response import FlapiParameterResponse


class GeneratedLayerMetadataResponse(BaseModel):
    description: str
    tags: List[str]
    sample_count: int
    dynamic_parameters: List[str] = []
    configurable_parameters: List[FlapiParameterResponse] = []
    requires_sample_polygon: bool = False
