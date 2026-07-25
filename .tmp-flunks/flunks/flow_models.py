from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel


class PackageInputCube(BaseModel):
    cube_name: str
    cube_parameter: str
    values: Optional[List[Any]] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class PackageOutputCube(BaseModel):
    cube_name: str


class MetaData(BaseModel):
    isPartialSuccess: Optional[str] = None


class FlowResults(BaseModel):
    metadata: MetaData
