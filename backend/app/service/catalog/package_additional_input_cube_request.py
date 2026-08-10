from typing import List, Literal

from pydantic import BaseModel, Field, model_validator


class PackageAdditionalInputCubeRequest(BaseModel):
    cube_name: str = Field(min_length=1, max_length=200)
    cube_parameter: str = Field(min_length=1, max_length=200)
    kind: Literal["time", "values"] = "time"
    values: List[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def require_values(self):
        if self.kind == "values" and not any(value.strip() for value in self.values):
            raise ValueError("values input requires at least one value")
        return self
