from typing import List

from pydantic import BaseModel


class CatalogLayer(BaseModel):
    id: str
    name: str
    description: str
    tags: List[str]
