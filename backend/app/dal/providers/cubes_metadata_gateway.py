"""Cubes metadata, parameter-definition, and autocomplete HTTP access."""

from typing import Dict, List
from urllib.parse import quote

import httpx

from app.bl.ports.layer_meta import LayerMeta
from app.bl.ports.layer_parameter_option import LayerParameterOption
from app.common.errors.provider_error import ProviderError
from app.dal.providers.cubes_client_factory import CubesClientFactory
from app.dal.providers.cubes_parameter_loader import CubesParameterLoader
from app.dal.providers.cubes_source import CubesSource


class CubesMetadataGateway:
    def __init__(
        self,
        clients: CubesClientFactory,
        source: CubesSource,
        parameters: CubesParameterLoader,
    ) -> None:
        self._clients = clients
        self._source = source
        self._parameters = parameters
        self._cache: Dict[str, dict] = {}

    def metadata(self, layer: LayerMeta) -> dict:
        database = quote(self._source.database_name(layer), safe="")
        cached = self._cache.get(database)
        if cached is not None:
            return cached
        payload = self._get_json(f"/cube/v1/{database}", "metadata")
        if not isinstance(payload, dict):
            raise ProviderError("Cubes metadata response must be a JSON object")
        payload["Parameters"] = self._parameters.load(
            database, payload.get("Parameters"), self._get_json
        )
        self._cache[database] = payload
        return payload

    def autocomplete(
        self, layer: LayerMeta, parameter_name: str
    ) -> List[LayerParameterOption]:
        database = quote(self._source.database_name(layer), safe="")
        parameter = quote(parameter_name, safe="")
        path = f"/cube/v1/{database}/autocomplete/{parameter}"
        payload = self._post_json(path, {}, "autocomplete")
        if not isinstance(payload, list):
            raise ProviderError("Cubes autocomplete response must be a JSON array")
        return [
            LayerParameterOption(
                value=str(item["Value"]), name=str(item.get("Name") or "")
            )
            for item in payload
            if isinstance(item, dict) and item.get("Value") not in (None, "")
        ]

    def _get_json(self, path: str, request_name: str) -> object:
        try:
            with self._clients.create() as client:
                response = client.get(path)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(
                f"Cubes {request_name} request failed ({path}): {exc}"
            ) from exc

    def _post_json(self, path: str, body: dict, request_name: str) -> object:
        try:
            with self._clients.create() as client:
                response = client.post(path, json=body)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(
                f"Cubes {request_name} request failed ({path}): {exc}"
            ) from exc
