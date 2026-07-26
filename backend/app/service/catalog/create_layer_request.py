from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CreateLayerRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    tags: List[str] = Field(default_factory=list)
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
    package_output_cube_name: Optional[str] = Field(default=None, max_length=200)
    entity_field: Optional[str] = Field(
        default=None, min_length=1, max_length=60
    )
    display_field: Optional[str] = Field(
        default=None, min_length=1, max_length=60
    )
    profiles: List[str] = Field(default_factory=list, max_length=10)
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
