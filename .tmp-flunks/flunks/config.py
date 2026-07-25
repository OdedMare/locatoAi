from typing import Any

from pydantic import BaseModel


class FlApiConfig(BaseModel):
    username: str
    token: str


class FlunksConfig(BaseModel):
    max_threads: int = 4


class FlunksPackageConfig(BaseModel):
    package_id: str
    package_name: str
    main_input_cube: Any
    output_cube: Any
