"""Layer-catalog HTTP controller."""

import json
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from app.bl.agent.generate_layer_metadata.layer_metadata_generator import LayerMetadataGenerator
from app.bl.catalog.mqs_sync.browse_mqs_layers import browse_mqs_layers
from app.bl.catalog.mqs_sync.sync_mqs_layers import sync_mqs_layers
from app.bl.catalog.tyche_activation import TYCHE_SOURCE, activate_tyche_layer
from app.bl.catalog.models.layer_meta import LayerMeta
from app.common.errors.provider_error import ProviderError
from app.service.catalog.catalog_layer import CatalogLayer
from app.service.catalog.create_layer_request import CreateLayerRequest
from app.service.catalog.cubes_autocomplete_option_response import CubesAutocompleteOptionResponse
from app.service.catalog.cubes_autocomplete_request import CubesAutocompleteRequest
from app.service.catalog.cubes_autocomplete_response import CubesAutocompleteResponse
from app.service.catalog.flapi_parameter_response import FlapiParameterResponse
from app.service.catalog.generate_layer_metadata_request import GenerateLayerMetadataRequest
from app.service.catalog.generated_layer_metadata_response import GeneratedLayerMetadataResponse
from app.service.catalog.layers_response import LayersResponse
from app.service.catalog.layer_fields_response import LayerFieldsResponse
from app.service.catalog.mqs_sync_response import MqsSyncResponse
from app.service.catalog.remote_mqs_layer_response import RemoteMqsLayerResponse
from app.service.catalog.remote_mqs_layers_response import RemoteMqsLayersResponse
from app.service.catalog.update_layer_request import UpdateLayerRequest

router = APIRouter()
_PARAMETER_PREFIX = "param_"
_PACKAGE_INPUT_PREFIX = "input_"
_TYCHE_FIELDS = {
    "geometry_field": "geometry",
    "geo_query_field": "location",
    "time_field": "eventTime",
    "entity_field": "",
}


class CatalogRouter:
    @staticmethod
    def list_layers(request: Request) -> LayersResponse:
        layers = request.app.state.catalog.list_layers()
        return LayersResponse(
            layers=[CatalogRouter.catalog_layer(layer) for layer in layers],
            count=len(layers),
        )

    @staticmethod
    def layer_fields(layer_id: str, request: Request) -> LayerFieldsResponse:
        schema = request.app.state.catalog.get_schema(layer_id)
        return LayerFieldsResponse(
            layer_id=layer_id,
            fields=[field.name for field in schema.fields],
        )

    @staticmethod
    def sync_mqs(request: Request) -> MqsSyncResponse:
        result = sync_mqs_layers(
            request.app.state.repository, request.app.state.mqs_provider
        )
        return MqsSyncResponse(
            added=result.added, updated=result.updated,
            skipped=result.skipped, total=result.total,
        )

    @staticmethod
    def list_remote_mqs_layers(request: Request) -> RemoteMqsLayersResponse:
        layers, skipped = browse_mqs_layers(request.app.state.mqs_provider)
        return RemoteMqsLayersResponse(
            layers=[CatalogRouter._remote_layer(layer) for layer in layers],
            count=len(layers), skipped=skipped,
        )

    @staticmethod
    def activate_tyche(request: Request) -> CatalogLayer:
        activated, created, sample_count = activate_tyche_layer(
            request.app.state.repository, request.app.state.tyche_provider,
        )
        request.app.state.request_log.info(
            "tyche_layer_activated", layer_id=activated.id, created=created,
            sample_count=sample_count, source_url=TYCHE_SOURCE,
        )
        return CatalogRouter.catalog_layer(activated)

    @classmethod
    def create_layer(
        cls, body: CreateLayerRequest, request: Request
    ) -> CatalogLayer:
        layer = cls._new_layer(body)
        try:
            created = request.app.state.catalog.add_layer(layer)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return cls.catalog_layer(created)

    @classmethod
    def update_layer(
        cls, layer_id: str, body: UpdateLayerRequest, request: Request,
    ) -> CatalogLayer:
        current = request.app.state.catalog.get_layer(layer_id)
        supplied = body.model_fields_set
        updated = request.app.state.catalog.update_layer_metadata(
            layer_id, body.name.strip(), body.description.strip(),
            cls.clean_tags(body.tags, 40),
            entity_field=(
                body.entity_field.strip() if body.entity_field
                else None if "entity_field" in supplied else current.entity_field
            ),
            display_field=(
                body.display_field.strip() if body.display_field
                else None if "display_field" in supplied else current.display_field
            ),
            profiles=(
                cls.clean_profiles(body.profiles)
                if body.profiles is not None else current.profiles
            ),
        )
        request.app.state.request_log.info(
            "catalog_layer_updated", layer_id=updated.id,
            name=updated.name, tag_count=len(updated.tags),
        )
        return cls.catalog_layer(updated)

    @staticmethod
    def delete_layer(layer_id: str, request: Request) -> None:
        deleted = request.app.state.catalog.delete_layer(layer_id)
        request.app.state.request_log.info(
            "catalog_layer_deleted", layer_id=deleted.id, name=deleted.name,
        )

    @classmethod
    def generate_metadata(
        cls, body: GenerateLayerMetadataRequest, request: Request
    ) -> GeneratedLayerMetadataResponse:
        generator: LayerMetadataGenerator = request.app.state.layer_metadata_generator
        result = generator.generate(
            name=body.name, provider_name=body.provider,
            source_url=cls.normalized_source(
                body.provider, body.source_url, body.cubes_query_mode,
                body.parameter_values(),
                flapi_resource_type=body.flapi_resource_type,
                package_parameters=body.package_parameters,
                package_query=body.package_query,
                tyche_geometry_field=body.tyche_geometry_field,
                tyche_geo_query_field=body.tyche_geo_query_field,
                tyche_time_field=body.tyche_time_field,
                tyche_entity_field=body.tyche_entity_field,
            ),
            sample_geometry=cls._sample_geometry(body),
        )
        return GeneratedLayerMetadataResponse(
            description=result.description, tags=result.tags,
            sample_count=result.sample_count,
            dynamic_parameters=result.dynamic_parameters,
            configurable_parameters=[
                FlapiParameterResponse(
                    name=item.name,
                    display_name=item.display_name,
                    description=item.description,
                    type=item.type,
                    required=item.required,
                    single_value=item.single_value,
                    ontology_type=item.ontology_type,
                    has_default=item.has_default,
                    dynamic=item.is_dynamic,
                    options=item.options,
                )
                for item in result.configurable_parameters
            ],
            requires_sample_polygon=result.requires_sample_polygon,
        )

    @staticmethod
    def _sample_geometry(body: GenerateLayerMetadataRequest):
        if body.provider.strip().lower() not in ("cubes", "flapi"):
            return None
        boundary = body.cubes_sample_boundary
        if boundary is None:
            return None
        geometry = boundary.to_shapely()
        if geometry.geom_type == "MultiPolygon" and len(geometry.geoms) == 1:
            return geometry.geoms[0]
        return geometry

    @classmethod
    def autocomplete(
        cls, body: CubesAutocompleteRequest, request: Request
    ) -> CubesAutocompleteResponse:
        layer = LayerMeta(
            id="autocomplete-preview", name="", provider="cubes",
            source_url=cls.normalized_source("cubes", body.source_url),
        )
        options = cls._autocomplete_options(
            request.app.state.flapi_provider, layer, body.parameter_name
        )
        return CubesAutocompleteResponse(options=[
            CubesAutocompleteOptionResponse(value=item.value, name=item.name)
            for item in options
        ])

    @staticmethod
    def _autocomplete_options(provider, layer, parameter_name):
        try:
            return provider.fetch_autocomplete_options(layer, parameter_name)
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(
                f"Could not fetch autocomplete options for '{parameter_name}'"
            ) from exc

    @classmethod
    def normalized_source(
        cls, provider: str, source_url: str, cubes_query_mode: str = "auto",
        cubes_parameters: Optional[Dict[str, str]] = None,
        cubes_dynamic_parameters: Optional[Dict[str, str]] = None,
        flapi_resource_type: str = "cube",
        package_parameters: Optional[Dict[str, Any]] = None,
        package_query: Optional[str] = None,
        tyche_geometry_field: Optional[str] = None,
        tyche_geo_query_field: Optional[str] = None,
        tyche_time_field: Optional[str] = None,
        tyche_entity_field: Optional[str] = None,
    ) -> str:
        source = source_url.strip()
        if provider.strip().lower() == "cubes":
            source = source if "://" in source else f"cubes://db/{source.strip('/')}"
            source = cls.with_cubes_mode(source, cubes_query_mode)
            values = cubes_parameters or cubes_dynamic_parameters or {}
            return cls.with_parameters(source, values)
        if provider.strip().lower() == "flapi":
            source = cls._flapi_source(source, flapi_resource_type)
            if cls._flapi_type(source) == "package":
                return cls.with_package_config(
                    source, package_parameters or {}, package_query
                )
            source = cls.with_cubes_mode(source, cubes_query_mode)
            return cls.with_parameters(
                source, cubes_parameters or cubes_dynamic_parameters or {}
            )
        if provider.strip().lower() == "tyche":
            source = source if "://" in source else f"tyche://{source.strip('/')}"
            return cls.with_tyche_fields(
                source, tyche_geometry_field,
                tyche_geo_query_field, tyche_time_field, tyche_entity_field,
            )
        return source

    @staticmethod
    def with_cubes_mode(source: str, mode: str) -> str:
        parsed = urlsplit(source)
        query = parse_qs(parsed.query, keep_blank_values=True)
        if mode == "auto":
            query.pop("query_mode", None)
        else:
            query["query_mode"] = [mode]
        return urlunsplit(parsed._replace(query=urlencode(query, doseq=True)))

    @staticmethod
    def with_parameters(source: str, parameters: Dict[str, str]) -> str:
        parsed = urlsplit(source)
        query = parse_qs(parsed.query, keep_blank_values=True)
        for key in [key for key in query if key.startswith(_PARAMETER_PREFIX)]:
            query.pop(key)
        for name, value in parameters.items():
            if name and value:
                query[f"{_PARAMETER_PREFIX}{name}"] = [value]
        return urlunsplit(parsed._replace(query=urlencode(query, doseq=True)))

    @staticmethod
    def with_tyche_fields(
        source: str, geometry_field: Optional[str],
        geo_query_field: Optional[str], time_field: Optional[str],
        entity_field: Optional[str] = None,
    ) -> str:
        parsed = urlsplit(source)
        query = parse_qs(parsed.query, keep_blank_values=True)
        values = (geometry_field, geo_query_field, time_field, entity_field)
        for (key, default), value in zip(_TYCHE_FIELDS.items(), values):
            if value is None:
                continue
            query.pop(key, None)
            cleaned = value.strip()
            if cleaned and cleaned != default:
                query[key] = [cleaned]
        return urlunsplit(parsed._replace(query=urlencode(query, doseq=True)))

    @staticmethod
    def with_package_config(
        source: str, parameters: Dict[str, Any],
        selected_query: Optional[str] = None,
    ) -> str:
        parsed = urlsplit(source)
        query = parse_qs(parsed.query, keep_blank_values=True)
        for key in [key for key in query if key.startswith(_PACKAGE_INPUT_PREFIX)]:
            query.pop(key)
        query.pop("query", None)
        for name, value in parameters.items():
            if name and value not in (None, ""):
                query[f"{_PACKAGE_INPUT_PREFIX}{name}"] = [
                    json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                ]
        if selected_query:
            query["query"] = [selected_query.strip()]
        return urlunsplit(parsed._replace(query=urlencode(query, doseq=True)))

    @classmethod
    def _flapi_source(cls, source: str, resource_type: str) -> str:
        if "://" in source:
            return source
        return f"flapi://{resource_type}/{source.strip('/')}"

    @staticmethod
    def _flapi_type(source: str) -> str:
        parsed = urlsplit(source)
        if parsed.scheme.casefold() == "package":
            return "package"
        return (
            "package"
            if parsed.scheme.casefold() == "flapi"
            and parsed.netloc.casefold() == "package"
            else "cube"
        )

    @staticmethod
    def clean_tags(tags: List[str], limit: int) -> List[str]:
        cleaned = (str(tag).strip()[:60] for tag in tags)
        return list(dict.fromkeys(tag for tag in cleaned if tag))[:limit]

    @staticmethod
    def clean_profiles(profiles: List[str]) -> List[str]:
        cleaned = (str(profile).strip()[:60] for profile in profiles)
        return list(dict.fromkeys(item for item in cleaned if item))[:10]

    @staticmethod
    def catalog_layer(layer: LayerMeta) -> CatalogLayer:
        return CatalogLayer(
            id=layer.id, name=layer.name,
            description=layer.description, tags=layer.tags,
            entity_field=layer.entity_field,
            display_field=layer.display_field,
            profiles=layer.profiles,
        )

    @classmethod
    def _new_layer(cls, body: CreateLayerRequest) -> LayerMeta:
        return LayerMeta(
            id=str(uuid4()), name=body.name.strip(),
            description=body.description.strip(),
            tags=cls.clean_tags(body.tags, 20),
            provider=body.provider.strip(),
            entity_field=body.entity_field.strip() if body.entity_field else None,
            display_field=body.display_field.strip() if body.display_field else None,
            profiles=cls.clean_profiles(body.profiles),
            source_url=cls.normalized_source(
                body.provider, body.source_url, body.cubes_query_mode,
                body.parameter_values(),
                flapi_resource_type=body.flapi_resource_type,
                package_parameters=body.package_parameters,
                package_query=body.package_query,
                tyche_geometry_field=body.tyche_geometry_field,
                tyche_geo_query_field=body.tyche_geo_query_field,
                tyche_time_field=body.tyche_time_field,
                tyche_entity_field=body.tyche_entity_field,
            ),
        )

    @staticmethod
    def _remote_layer(layer) -> RemoteMqsLayerResponse:
        return RemoteMqsLayerResponse(
            id=layer.id, name=layer.name, description=layer.description,
            tags=layer.tags, provider=layer.provider, source_url=layer.source_url,
        )


list_layers = CatalogRouter.list_layers
layer_fields = CatalogRouter.layer_fields
sync_mqs = CatalogRouter.sync_mqs
list_remote_mqs_layers = CatalogRouter.list_remote_mqs_layers
activate_tyche = CatalogRouter.activate_tyche
create_layer = CatalogRouter.create_layer
update_layer = CatalogRouter.update_layer
delete_layer = CatalogRouter.delete_layer
generate_layer_metadata = CatalogRouter.generate_metadata
autocomplete_cubes_parameter = CatalogRouter.autocomplete
_with_cubes_mode = CatalogRouter.with_cubes_mode
_with_cubes_parameters = CatalogRouter.with_parameters
_with_cubes_dynamic_parameters = CatalogRouter.with_parameters
_with_tyche_fields = CatalogRouter.with_tyche_fields
_normalized_source = CatalogRouter.normalized_source
_clean_tags = CatalogRouter.clean_tags
_catalog_layer = CatalogRouter.catalog_layer

router.add_api_route("/api/layers", list_layers, methods=["GET"], response_model=LayersResponse)
router.add_api_route(
    "/api/layers/{layer_id}/fields", layer_fields,
    methods=["GET"], response_model=LayerFieldsResponse,
)
router.add_api_route("/api/layers/sync-mqs", sync_mqs, methods=["POST"], response_model=MqsSyncResponse)
router.add_api_route("/api/layers/mqs", list_remote_mqs_layers, methods=["GET"], response_model=RemoteMqsLayersResponse)
router.add_api_route("/api/layers/activate-tyche", activate_tyche, methods=["POST"], response_model=CatalogLayer)
router.add_api_route("/api/layers", create_layer, methods=["POST"], response_model=CatalogLayer, status_code=201)
router.add_api_route("/api/layers/{layer_id}", update_layer, methods=["PUT"], response_model=CatalogLayer)
router.add_api_route(
    "/api/layers/{layer_id}", delete_layer, methods=["DELETE"], status_code=204,
)
router.add_api_route("/api/layers/generate-metadata", generate_layer_metadata, methods=["POST"], response_model=GeneratedLayerMetadataResponse)
router.add_api_route("/api/layers/autocomplete-parameter", autocomplete_cubes_parameter, methods=["POST"], response_model=CubesAutocompleteResponse)
