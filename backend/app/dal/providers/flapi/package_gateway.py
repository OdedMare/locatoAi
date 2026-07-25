"""Flow Package metadata discovery and flunks-backed execution."""

import logging
from typing import Any, Dict, List, Optional
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
        static_parameters: Dict[str, Any],
        queries: List[str],
        output_fields: Optional[List[str]] = None,
    ) -> List[dict]:
        package_id = self._source.package_id(layer)
        runner = self._build_runner(
            package_id, input_cube, static_parameters, queries, output_fields,
        )
        try:
            flow_results = runner.run()
        except Exception as exc:
            raise ProviderError(
                f"FLAPI package request failed (package/v3/{package_id}): {exc}"
            ) from exc
        finally:
            self.success_chunks = getattr(runner, "success_chunks", 0)
            self.failed_chunks = getattr(runner, "failed_chunks", 0)
        return self._records(flow_results, queries)

    def _build_runner(
        self, package_id, input_cube, static_parameters, queries, output_fields=None,
    ):
        settings = self._clients.require_settings(require_username=True)
        flapi_config = FlapiConfig(
            username=settings.flapi_username, token=settings.cubes_token,
            base_url=settings.cubes_base_url,
        )
        output_cube = PackageOutputCube(
            cube_name=queries[0] if queries else "output",
            cube_fields=output_fields or [],
        )
        package_config = FlunksPackageConfig(
            package_id=package_id,
            main_input_cube=input_cube,
            output_cube=output_cube,
            static_parameters=static_parameters,
        )
        return FlunksRunner(
            flapi_config=flapi_config,
            package_config=package_config,
            flunks_config=self._flunks_config,
            exceptions_config=self._exceptions_config,
        )

    def _records(self, flow_results: Any, selected: List[str]) -> List[dict]:
        results = self._results_dict(flow_results)
        self._inspect_metadata(flow_results)
        missing = [query for query in selected if query not in results]
        if missing:
            raise ProviderError(
                "FLAPI package did not return selected queries: "
                + ", ".join(missing)
            )
        rows: List[dict] = []
        for query, result in results.items():
            if selected and query not in selected:
                continue
            rows.extend(self._query_records(str(query), result))
            if len(rows) > self._MAX_ROWS:
                raise ProviderError(
                    f"FLAPI package exceeded the {self._MAX_ROWS} row safety limit"
                )
        return rows

    @staticmethod
    def _results_dict(flow_results: Any) -> dict:
        results = getattr(flow_results, "results", flow_results)
        if not isinstance(results, dict):
            raise ProviderError("FLAPI package response has no results object")
        return results

    def _query_records(self, query: str, result: object) -> List[dict]:
        try:
            records = self._rows.records(result)
        except ProviderError:
            self._logger.warning(
                "Ignoring unrecognized Flow Package query result",
                extra={"query": query},
            )
            return []
        return [dict(record, _package_query=query) for record in records]

    def _inspect_metadata(self, flow_results: Any) -> None:
        metadata = getattr(flow_results, "metadata", None)
        if metadata is None:
            return
        trace_id = getattr(metadata, "traceId", None)
        if getattr(metadata, "isPartialSuccess", False):
            self._logger.warning(
                "FLAPI package partially succeeded",
                extra={
                    "trace_id": trace_id,
                    "failed_queries": getattr(
                        metadata, "partialSuccessFailedQueries", []
                    ),
                },
            )
        limited = getattr(metadata, "queriesReachedResultsLimit", None) or []
        if limited:
            self._logger.warning(
                "FLAPI package queries reached their result limit",
                extra={"trace_id": trace_id, "queries": limited},
            )
