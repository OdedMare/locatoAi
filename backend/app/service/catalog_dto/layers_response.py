from typing import List

from pydantic import BaseModel

from app.service.catalog_dto.catalog_layer import CatalogLayer


class LayersResponse(BaseModel):
    layers: List[CatalogLayer]
    count: int
