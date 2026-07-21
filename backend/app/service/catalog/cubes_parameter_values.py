"""Resolved Cubes parameter values."""

from typing import Dict

from pydantic import BaseModel, Field


class CubesParameterValues(BaseModel):
    cubes_parameters: Dict[str, str] = Field(default_factory=dict, max_length=20)
    cubes_dynamic_parameters: Dict[str, str] = Field(
        default_factory=dict, max_length=20
    )
    """Deprecated request name retained for existing clients."""

    def parameter_values(self) -> Dict[str, str]:
        return {**self.cubes_dynamic_parameters, **self.cubes_parameters}
