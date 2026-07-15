"""GET /api/layers — the public layer catalog.

Lets users browse which data layers exist (name/description/tags) so
they know what they can ask about. Metadata only — never features.
"""

from typing import List
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.bl.agent.generate_layer_metadata import LayerMetadataGenerator
from app.bl.catalog.mqs_sync import browse_mqs_layers, sync_mqs_layers
from app.bl.ports import LayerMeta

router = APIRouter()


class CatalogLayer(BaseModel):
    id: str
    name: str
    description: str
    tags: List[str]


class LayersResponse(BaseModel):
    layers: List[CatalogLayer]
    count: int


class MqsSyncResponse(BaseModel):
    added: int
    updated: int
    skipped: int
    total: int


class RemoteMqsLayerResponse(BaseModel):
    id: str
    name: str
    description: str
    tags: List[str]
    provider: str
    source_url: str


class RemoteMqsLayersResponse(BaseModel):
    layers: List[RemoteMqsLayerResponse]
    count: int
    skipped: int


class CreateLayerRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    tags: List[str] = []
    provider: str = Field(default="mqs", min_length=1, max_length=50)
    source_url: str = Field(min_length=1, max_length=2000)


class GenerateLayerMetadataRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    provider: str = Field(default="mqs", min_length=1, max_length=50)
    source_url: str = Field(min_length=1, max_length=2000)


class GeneratedLayerMetadataResponse(BaseModel):
    description: str
    tags: List[str]
    sample_count: int


def _normalized_source(provider: str, source_url: str) -> str:
    source = source_url.strip()
    if provider.strip().lower() == "cubes" and "://" not in source:
        return f"cubes://db/{source.strip('/')}"
    return source


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


@router.post("/api/layers/sync-mqs", response_model=MqsSyncResponse)
def sync_mqs(request: Request) -> MqsSyncResponse:
    """Pull the MQS layer inventory into the catalog (upsert by source_url).
    A ProviderError (e.g. mqs_base_url unset) maps to 502 via main.py."""
    result = sync_mqs_layers(
        request.app.state.repository, request.app.state.mqs_provider
    )
    return MqsSyncResponse(
        added=result.added,
        updated=result.updated,
        skipped=result.skipped,
        total=result.total,
    )


@router.get("/api/layers/mqs", response_model=RemoteMqsLayersResponse)
def list_remote_mqs_layers(request: Request) -> RemoteMqsLayersResponse:
    """Browse MQS metadata without inserting anything into the catalog."""
    layers, skipped = browse_mqs_layers(request.app.state.mqs_provider)
    return RemoteMqsLayersResponse(
        layers=[
            RemoteMqsLayerResponse(
                id=layer.id,
                name=layer.name,
                description=layer.description,
                tags=layer.tags,
                provider=layer.provider,
                source_url=layer.source_url,
            )
            for layer in layers
        ],
        count=len(layers),
        skipped=skipped,
    )


@router.post("/api/layers", response_model=CatalogLayer, status_code=201)
def create_layer(body: CreateLayerRequest, request: Request) -> CatalogLayer:
    tags = list(dict.fromkeys(tag.strip() for tag in body.tags if tag.strip()))[:20]
    layer = LayerMeta(
        id=str(uuid4()),
        name=body.name.strip(),
        description=body.description.strip(),
        tags=tags,
        provider=body.provider.strip(),
        source_url=_normalized_source(body.provider, body.source_url),
    )
    try:
        created = request.app.state.catalog.add_layer(layer)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return CatalogLayer(
        id=created.id,
        name=created.name,
        description=created.description,
        tags=created.tags,
    )


@router.post(
    "/api/layers/generate-metadata", response_model=GeneratedLayerMetadataResponse
)
def generate_layer_metadata(
    body: GenerateLayerMetadataRequest, request: Request
) -> GeneratedLayerMetadataResponse:
    """Generate suggestions only; the user can edit them before layer creation."""
    generator: LayerMetadataGenerator = request.app.state.layer_metadata_generator
    result = generator.generate(
        name=body.name, provider_name=body.provider,
        source_url=_normalized_source(body.provider, body.source_url),
    )
    return GeneratedLayerMetadataResponse(
        description=result.description,
        tags=result.tags,
        sample_count=result.sample_count,
    )
