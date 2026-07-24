from typing import Any, Dict, Optional

from pydantic import Field

from app.service.catalog.cubes_parameter_values import CubesParameterValues
from app.service.catalog.cubes_query_mode import CubesQueryMode
from app.service.catalog.flapi_resource_type import FlapiResourceType
from app.service.shared.geo_json_multi_polygon import GeoJSONMultiPolygon


class GenerateLayerMetadataRequest(CubesParameterValues):
    name: str = Field(min_length=1, max_length=200)
    provider: str = Field(default="mqs", min_length=1, max_length=50)
    source_url: str = Field(min_length=1, max_length=2000)
    flapi_resource_type: FlapiResourceType = "cube"
    cubes_query_mode: CubesQueryMode = "auto"
    package_parameters: Dict[str, Any] = Field(
        default_factory=dict, max_length=50
    )
    package_query: Optional[str] = Field(default=None, max_length=200)
    cubes_sample_boundary: Optional[GeoJSONMultiPolygon] = None
