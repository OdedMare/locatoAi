"""GET /api/layers — the public layer catalog.

Lets users browse which data layers exist (name/description/tags) so
they know what they can ask about. Metadata only — never features.
"""

from typing import List

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class CatalogLayer(BaseModel):
    id: str
    name: str
    description: str
    tags: List[str]


class LayersResponse(BaseModel):
    layers: List[CatalogLayer]
    count: int


@router.get("/api/layers", response_model=LayersResponse)
def list_layers(request: Request) -> LayersResponse:
    layers = request.app.state.catalog.list_layers()
    return LayersResponse(
        layers=[
            CatalogLayer(
                id=layer.id,
                name=layer.name,
                description=layer.description,
                tags=layer.tags,
            )
            for layer in layers
        ],
        count=len(layers),
    )
