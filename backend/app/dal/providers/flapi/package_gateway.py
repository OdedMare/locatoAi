"""Flow Package metadata discovery and flunks-backed execution."""

import logging
from typing import List, Optional
from urllib.parse import quote

import httpx
from flunks import FlunksRunner, PackageInputCube, PackageOutputCube
from flunks.config import (
    FlapiConfig, FlunksConfig, FlunksExceptionsConfig, FlunksPackageConfig,
)

from app.bl.catalog.models.layer_meta import LayerMeta
from app.common.errors.provider_error import ProviderError
from app.dal.providers.flapi.client_factory import FlapiClientFactory
from app.dal.providers.flapi.schema_mapper import FlapiSchemaMapper
from app.dal.providers.flapi.source import FlapiSource


class FlowPackageGateway:
    _REQUEST_TIMEOUT_SECONDS = 60
    _MAX_ROWS = 100000

    def __init__(
        self,
        clients: FlapiClientFactory,
        source: FlapiSource,
        rows: FlapiSchemaMapper,
        flunks_config: FlunksConfig = None,
        exceptions_config: FlunksExceptionsConfig = None,
    ) -> None:
        self._clients = clients
        self._source = source
        self._rows = rows
        self._flunks_config = flunks_config or FlunksConfig()
        self._exceptions_config = exceptions_config or FlunksExceptionsConfig()
        self._logger = logging.getLogger(__name__)
        self.success_chunks = 0
        self.failed_chunks = 0

    def definitions(self, layer: LayerMeta) -> object:
        package_id = quote(self._source.package_id(layer), safe="")
        try:
            with self._clients.create(require_username=True) as client:
                response = client.request(
                    "GET", f"/package/v1/quick/{package_id}",
                    timeout=self._REQUEST_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            raise ProviderError(
                f"FLAPI package request failed (/package/v1/quick/{package_id}): "
                f"{exc.response.status_code} {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"FLAPI package request failed (/package/v1/quick/{package_id}): {exc}"
            ) from exc
        except ValueError as exc:
            raise ProviderError(
                f"FLAPI package returned invalid JSON (/package/v1/quick/{package_id})"
            ) from exc

    def execute(
        self,
        layer: LayerMeta,
        input_cube: PackageInputCube,
        output_cube_name: Optional[str],
    ) -> List[dict]:
        package_id = self._source.package_id(layer)
        runner = self._build_runner(package_id, input_cube, output_cube_name)
        try:
            records = runner.run()
        except Exception as exc:
            raise ProviderError(
                f"FLAPI package request failed (package/v3/{package_id}): {exc}"
            ) from exc
        finally:
            self.success_chunks = getattr(runner, "success_chunks", 0)
            self.failed_chunks = getattr(runner, "failed_chunks", 0)
        return self._records(records, output_cube_name)

    def _build_runner(self, package_id, input_cube, output_cube_name):
        settings = self._clients.require_settings(require_username=True)
        flapi_config = FlapiConfig(
            username=settings.flapi_username, token=settings.cubes_token,
            base_url=settings.cubes_base_url,
        )
        if not output_cube_name:
            raise ProviderError("Flow Package output cube name is required")
        output_cube = PackageOutputCube(cube_name=output_cube_name)
        package_config = FlunksPackageConfig(
            package_id=package_id,
            main_input_cube=input_cube,
            output_cube=output_cube,
        )
        return FlunksRunner(
            flapi_config=flapi_config,
            package_config=package_config,
            flunks_config=self._flunks_config,
            exceptions_config=self._exceptions_config,
        )

    def _records(self, records: object, output_cube_name: str) -> List[dict]:
        if not isinstance(records, list):
            raise ProviderError("FLAPI package response is not a list of records")
        rows: List[dict] = []
        for record in records:
            if not isinstance(record, dict):
                self._logger.warning(
                    "Ignoring non-dict Flow Package record",
                    extra={"output_cube": output_cube_name},
                )
                continue
            rows.append(dict(record, _package_query=output_cube_name))
            if len(rows) > self._MAX_ROWS:
                raise ProviderError(
                    f"FLAPI package exceeded the {self._MAX_ROWS} row safety limit"
                )
        return rows
