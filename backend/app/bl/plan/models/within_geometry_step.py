from typing import Literal

from pydantic import BaseModel


class WithinGeometryStep(BaseModel):
    id: str
    op: Literal["within_geometry"]
    input: str
    geometry: Literal["user_polygon"] = "user_polygon"
