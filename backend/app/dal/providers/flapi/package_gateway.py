"""flunks-backed Flow Package execution."""

import logging
from typing import List, Optional

from flunks import FlunksRunner, PackageInputCube, PackageOutputCube
from flunks.config import (
    FlapiConfig, FlunksConfig, FlunksExceptionsConfig, FlunksPackageConfig,
)

from app.bl.catalog.models.layer_meta import LayerMeta
from app.common.errors.provider_error import ProviderError
from app.dal.providers.flapi.client_factory import FlapiClientFactory
from app.dal.providers.flapi.flunks_metadata_patch import FlunksMetadataPatch
from app.dal.providers.flapi.package_debug import FlowPackageDebug
from app.dal.providers.flapi.package_records import FlowPackageRecords
from app.dal.providers.flapi.schema_mapper import FlapiSchemaMapper
from app.dal.providers.flapi.source import FlapiSource

# FLAPI returns isPartialSuccess as a JSON boolean while flunks types it as str.
# Applied at import, before any FlunksRunner parses a response. The result is
# logged because a no-op patch is otherwise indistinguishable from a working one
# — and its absence only surfaces later as a FlowResults ValidationError.
logging.getLogger(__name__).info(
    "FLAPI flunks metadata patch applied=%s", FlunksMetadataPatch.apply()
)


class FlowPackageGateway:
    """Runs a Flow Package through flunks.

    flunks owns the whole HTTP conversation with FLAPI — endpoint routing,
    chunking, retries, and exception mapping. This class only translates our
    catalog/settings types into flunks config and normalizes the records it
    returns, so no FLAPI route or API version appears here.
    """

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

    def execute(
        self,
        layer: LayerMeta,
        input_cube: PackageInputCube,
        output_cube_name: Optional[str],
    ) -> List[dict]:
        package_id = self._source.package_id(layer)
        self._logger.info(
            "FLAPI package RUN id=%s layer=%s output_cube=%r %s",
            package_id, layer.id, output_cube_name,
            FlowPackageDebug.input_cube(input_cube),
        )
        runner = self._build_runner(package_id, input_cube, output_cube_name)
        try:
            records = runner.run()
        except Exception as exc:
            # exc_info: a ValidationError raised inside flunks' own response
            # parsing is indistinguishable from a FLAPI-side rejection without
            # the traceback showing which frame actually raised.
            self._logger.error(
                "FLAPI package FAILED id=%s layer=%s %s -> %s",
                package_id, layer.id,
                FlowPackageDebug.input_cube(input_cube),
                FlowPackageDebug.exception(exc),
                exc_info=True,
            )
            raise ProviderError(
                f"FLAPI package {package_id} execution failed: {exc}"
            ) from exc
        finally:
            self.success_chunks = getattr(runner, "success_chunks", 0)
            self.failed_chunks = getattr(runner, "failed_chunks", 0)
            self._logger.info(
                "FLAPI package CHUNKS id=%s success=%s failed=%s",
                package_id, self.success_chunks, self.failed_chunks,
            )
        rows = self._records(records, output_cube_name)
        self._logger.info(
            "FLAPI package OK id=%s layer=%s %s",
            package_id, layer.id, FlowPackageDebug.records(rows),
        )
        return rows

    def _build_runner(self, package_id, input_cube, output_cube_name):
        settings = self._clients.require_settings(require_username=True)
        # Credentials are never logged — only whether they are present.
        self._logger.info(
            "FLAPI package CONFIG id=%s base_url=%s username=%s token_set=%s",
            package_id, settings.cubes_base_url, settings.flapi_username,
            bool(settings.cubes_token),
        )
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
        records = self._normalized(records)
        if not isinstance(records, list):
            # The type alone is the diagnosis: an envelope/dict here means flunks
            # changed its return contract, not that the package returned nothing.
            self._logger.error(
                "FLAPI package response type=%s value=%.200r",
                type(records).__name__, records,
            )
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
