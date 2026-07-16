"""GET /api/layers — the public layer catalog.

Lets users browse which data layers exist (name/description/tags) so
they know what they can ask about. Metadata only — never features.
"""

from typing import List
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from app.bl.agent.generate_layer_metadata.layer_metadata_generator import (
    LayerMetadataGenerator,
)
from app.bl.catalog.mqs_sync.browse_mqs_layers import browse_mqs_layers
from app.bl.catalog.mqs_sync.sync_mqs_layers import sync_mqs_layers
from app.bl.catalog.tyche_activation import TYCHE_SOURCE, activate_tyche_layer
from app.bl.ports.layer_meta import LayerMeta
from app.service.catalog_dto.catalog_layer import CatalogLayer
from app.service.catalog_dto.create_layer_request import CreateLayerRequest
from app.service.catalog_dto.generate_layer_metadata_request import (
    GenerateLayerMetadataRequest,
)
from app.service.catalog_dto.generated_layer_metadata_response import (
    GeneratedLayerMetadataResponse,
)
from app.service.catalog_dto.layers_response import LayersResponse
from app.service.catalog_dto.mqs_sync_response import MqsSyncResponse
from app.service.catalog_dto.remote_mqs_layer_response import RemoteMqsLayerResponse
from app.service.catalog_dto.remote_mqs_layers_response import (
    RemoteMqsLayersResponse,
)
from app.service.catalog_dto.update_layer_request import UpdateLayerRequest

router = APIRouter()


def _with_cubes_mode(source: str, mode: str) -> str:
    parsed = urlsplit(source)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if mode == "auto":
        query.pop("query_mode", None)
    else:
        query["query_mode"] = [mode]
    return urlunsplit(parsed._replace(query=urlencode(query, doseq=True)))


def _normalized_source(
    provider: str, source_url: str, cubes_query_mode: str = "auto",
) -> str:
    source = source_url.strip()
    if provider.strip().lower() == "cubes":
        if "://" not in source:
            source = f"cubes://db/{source.strip('/')}"
        return _with_cubes_mode(source, cubes_query_mode)
    if provider.strip().lower() == "tyche" and "://" not in source:
        return f"tyche://{source.strip('/')}"
    return source


def _clean_tags(tags: List[str], limit: int) -> List[str]:
    cleaned = (str(tag).strip()[:60] for tag in tags)
    return list(dict.fromkeys(tag for tag in cleaned if tag))[:limit]


def _catalog_layer(layer: LayerMeta) -> CatalogLayer:
    return CatalogLayer(
        id=layer.id, name=layer.name,
        description=layer.description, tags=layer.tags,
    )


@router.get("/api/layers", response_model=LayersResponse)
def list_layers(request: Request) -> LayersResponse:
    layers = request.app.state.catalog.list_layers()
    return LayersResponse(
        layers=[
            _catalog_layer(layer)
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


@router.post("/api/layers/activate-tyche", response_model=CatalogLayer)
def activate_tyche(request: Request) -> CatalogLayer:
    """Probe Tyche and idempotently activate its Our Forces catalog layer."""
    activated, created, sample_count = activate_tyche_layer(
        request.app.state.repository, request.app.state.tyche_provider,
    )
    request.app.state.request_log.info(
        "tyche_layer_activated", layer_id=activated.id, created=created,
        sample_count=sample_count, source_url=TYCHE_SOURCE,
    )
    return _catalog_layer(activated)


@router.post("/api/layers", response_model=CatalogLayer, status_code=201)
def create_layer(body: CreateLayerRequest, request: Request) -> CatalogLayer:
    tags = _clean_tags(body.tags, 20)
    layer = LayerMeta(
        id=str(uuid4()),
        name=body.name.strip(),
        description=body.description.strip(),
        tags=tags,
        provider=body.provider.strip(),
        source_url=_normalized_source(
            body.provider, body.source_url, body.cubes_query_mode),
    )
    try:
        created = request.app.state.catalog.add_layer(layer)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _catalog_layer(created)


@router.put("/api/layers/{layer_id}", response_model=CatalogLayer)
def update_layer(
    layer_id: str, body: UpdateLayerRequest, request: Request,
) -> CatalogLayer:
    updated = request.app.state.catalog.update_layer_metadata(
        layer_id, body.name.strip(), body.description.strip(),
        _clean_tags(body.tags, 40),
    )
    request.app.state.request_log.info(
        "catalog_layer_updated", layer_id=updated.id,
        name=updated.name, tag_count=len(updated.tags),
    )
    return _catalog_layer(updated)


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
        source_url=_normalized_source(
            body.provider, body.source_url, body.cubes_query_mode),
    )
    return GeneratedLayerMetadataResponse(
        description=result.description,
        tags=result.tags,
        sample_count=result.sample_count,
    )
