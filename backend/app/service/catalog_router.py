"""GET /api/layers — the public layer catalog.

Lets users browse which data layers exist (name/description/tags) so
they know what they can ask about. Metadata only — never features.
"""

from uuid import uuid4
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, HTTPException, Request

from app.bl.agent.generate_layer_metadata.layer_metadata_generator import (
    LayerMetadataGenerator,
)
from app.bl.catalog.mqs_sync.browse_mqs_layers import browse_mqs_layers
from app.bl.catalog.mqs_sync.sync_mqs_layers import sync_mqs_layers
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

router = APIRouter()

_TYCHE_LAYER_NAME = "כוחותינו"
_TYCHE_SOURCE = "tyche://ourforces"
_TYCHE_DESCRIPTION = "מיקומים ואירועי זמן של כוחותינו ממערכת Tyche"
_TYCHE_TAGS = [
    "כוחותינו", "כוחות", "רכב", "יחידות", "מיקום בזמן אמת",
    "our forces", "vehicles", "units", "live location", "tyche",
]


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


@router.post("/api/layers/activate-tyche", response_model=CatalogLayer)
def activate_tyche(request: Request) -> CatalogLayer:
    """Probe Tyche and idempotently activate its Our Forces catalog layer."""
    layer = LayerMeta(
        id=str(uuid4()), name=_TYCHE_LAYER_NAME,
        description=_TYCHE_DESCRIPTION, tags=_TYCHE_TAGS,
        provider="tyche", source_url=_TYCHE_SOURCE,
    )
    sample = request.app.state.tyche_provider.fetch_features(layer, limit=1)
    activated, created = request.app.state.repository.upsert_layer(layer)
    persisted = request.app.state.repository.get_layer(activated.id) or activated
    request.app.state.request_log.info(
        "tyche_layer_activated", layer_id=persisted.id, created=created,
        sample_count=len(sample), source_url=_TYCHE_SOURCE,
    )
    return CatalogLayer(
        id=persisted.id, name=persisted.name,
        description=persisted.description, tags=persisted.tags,
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
        source_url=_normalized_source(
            body.provider, body.source_url, body.cubes_query_mode),
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
        source_url=_normalized_source(
            body.provider, body.source_url, body.cubes_query_mode),
    )
    return GeneratedLayerMetadataResponse(
        description=result.description,
        tags=result.tags,
        sample_count=result.sample_count,
    )
