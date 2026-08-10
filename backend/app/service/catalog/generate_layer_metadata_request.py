from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.service.shared.geo_json_multi_polygon import GeoJSONMultiPolygon
from app.service.catalog.package_additional_input_cube_request import (
    PackageAdditionalInputCubeRequest,
)


class GenerateLayerMetadataRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    provider: str = Field(default="mqs", min_length=1, max_length=50)
    source_url: str = Field(min_length=1, max_length=2000)
    package_parameters: Dict[str, Any] = Field(
        default_factory=dict, max_length=50
    )
    package_query: Optional[str] = Field(default=None, max_length=200)
    package_input_cube_name: Optional[str] = Field(default=None, max_length=200)
    package_input_cube_parameter: Optional[str] = Field(
        default=None, max_length=200
    )
    package_input_cube_kind: Optional[str] = Field(default=None, max_length=10)
    package_additional_input_cubes: List[
        PackageAdditionalInputCubeRequest
    ] = Field(default_factory=list, max_length=20)
    package_output_cube_name: Optional[str] = Field(default=None, max_length=200)
    cubes_sample_boundary: Optional[GeoJSONMultiPolygon] = None
    tyche_geometry_field: Optional[str] = Field(
        default=None, min_length=1, max_length=200
    )
    tyche_geo_query_field: Optional[str] = Field(
        default=None, min_length=1, max_length=200
    )
    tyche_time_field: Optional[str] = Field(
        default=None, min_length=1, max_length=200
    )
    tyche_time_from_field: Optional[str] = Field(
        default=None, max_length=200
    )
    tyche_time_to_field: Optional[str] = Field(
        default=None, max_length=200
    )
    tyche_entity_field: Optional[str] = Field(
        default=None, min_length=1, max_length=200
    )
    tyche_parameters: Dict[str, str] = Field(
        default_factory=dict, max_length=50
    )
