"""Run a Flow Package and normalize flunks' DataFrame."""

import logging
from typing import List, Optional

from flunks import FlunksRunner
from flunks.config import FlApiConfig, FlunksConfig, FlunksPackageConfig
from flunks.flow_models import PackageInputCube, PackageOutputCube

from app.bl.catalog.models.layer_meta import LayerMeta
from app.common.errors.provider_error import ProviderError
from app.dal.providers.flapi.client_factory import FlapiClientFactory
from app.dal.providers.flapi.flunks_metadata_patch import FlunksMetadataPatch
from app.dal.providers.flapi.package_debug import FlowPackageDebug
from app.dal.providers.flapi.package_records import FlowPackageRecords
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

    def __init__(
        self, clients: FlapiClientFactory, source: FlapiSource,
    ) -> None:
        self._clients = clients
        self._source = source
        self._logger = logging.getLogger(__name__)
        self.success_chunks = 0
        self.failed_chunks = 0

    def execute(
        self, layer: LayerMeta, input_cube: PackageInputCube,
        output_cube_name: Optional[str],
    ) -> List[dict]:
        package_id = self._source.package_id(layer)
        self._logger.info(
            "FLAPI package RUN id=%s layer=%s output_cube=%r %s",
            package_id, layer.id, output_cube_name,
            FlowPackageDebug.input_cube(input_cube),
        )
        runner = self._build_runner(package_id, input_cube, output_cube_name)
        result = self._run(
            runner, package_id, layer, input_cube, output_cube_name
        )
        rows = self._records(result, output_cube_name)
        self._logger.info(
            "FLAPI package OK id=%s layer=%s %s",
            package_id, layer.id, FlowPackageDebug.records(rows),
        )
        return rows

    def _run(self, runner, package_id, layer, input_cube, output_cube_name):
        identifiers = FlowPackageDebug.identifiers(
            package_id, input_cube, output_cube_name
        )
        try:
            return runner.run()
        except Exception as exc:
            detail = FlowPackageDebug.exception(exc)
            self._logger.error(
                "FLAPI package FAILED layer=%s %s -> %s",
                layer.id, identifiers, detail,
            )
            self._logger.debug("Full flunks failure", exc_info=True)
            raise ProviderError(
                f"FLAPI {identifiers} failed: {detail}"
            ) from exc
        finally:
            self._remember_chunks(runner, package_id)

    def _remember_chunks(self, runner, package_id) -> None:
        self.success_chunks = getattr(runner, "success_chunks", 0)
        self.failed_chunks = getattr(runner, "failed_chunks", 0)
        self._logger.info(
            "FLAPI package CHUNKS id=%s success=%s failed=%s",
            package_id, self.success_chunks, self.failed_chunks,
        )

    def _build_runner(self, package_id, input_cube, output_cube_name):
        settings = self._clients.require_settings(require_username=True)
        flapi_config = self._flapi_config(settings)
        package_config = self._package_config(
            package_id, input_cube, output_cube_name
        )
        self._logger.info(
            "FLAPI flunks INPUT %s",
            FlowPackageDebug.runner_input(flapi_config, package_config),
        )
        return FlunksRunner(
            flapi_config=flapi_config, package_config=package_config,
            flunks_config=FlunksConfig(),
        )

    @staticmethod
    def _flapi_config(settings):
        return FlApiConfig(
            username=settings.flapi_username, token=settings.cubes_token,
        )

    @staticmethod
    def _package_config(package_id, input_cube, output_cube_name):
        if not output_cube_name:
            raise ProviderError("Flow Package output cube name is required")
        return FlunksPackageConfig(
            package_id=package_id, package_name="",
            main_input_cube=input_cube,
            output_cube=PackageOutputCube(cube_name=output_cube_name),
        )

    def _records(self, result: object, output_cube_name: str) -> List[dict]:
        self._logger.info(
            "FLAPI package response is a DataFrame rows=%s",
            FlowPackageRecords.row_count(result),
        )
        rows = FlowPackageRecords.normalize(result)
        return [dict(row, _package_query=output_cube_name) for row in rows]
