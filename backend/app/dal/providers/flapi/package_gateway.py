"""Flow Package metadata and execution HTTP boundary."""

import logging
from typing import List
from urllib.parse import quote

import httpx

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
    ) -> None:
        self._clients = clients
        self._source = source
        self._rows = rows
        self._logger = logging.getLogger(__name__)

    def definitions(self, layer: LayerMeta) -> object:
        package_id = quote(self._source.package_id(layer), safe="")
        return self._request("GET", f"/package/v1/quick/{package_id}")

    def execute(self, layer: LayerMeta, body: dict) -> List[dict]:
        package_id = quote(self._source.package_id(layer), safe="")
        queries = self._source.package_queries(layer)
        payload = self._request(
            "POST", f"/package/v3/{package_id}", body,
            self._source.execution_params(layer),
        )
        return self._records(payload, queries)

    def _request(self, method, path, body=None, params=None):
        try:
            with self._clients.create(require_username=True) as client:
                response = client.request(
                    method, path, json=body, params=params,
                    timeout=self._REQUEST_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            self._log_failure_trace(exc.response)
            detail = exc.response.text[:500]
            raise ProviderError(
                f"FLAPI package request failed ({path}): "
                f"{exc.response.status_code} {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                f"FLAPI package request failed ({path}): {exc}"
            ) from exc
        except ValueError as exc:
            raise ProviderError(
                f"FLAPI package returned invalid JSON ({path})"
            ) from exc

    def _records(self, payload: object, selected: List[str]) -> List[dict]:
        if not isinstance(payload, dict) or not isinstance(
            payload.get("results"), dict
        ):
            raise ProviderError("FLAPI package response has no results object")
        self._inspect_metadata(payload.get("metadata"))
        missing = [query for query in selected if query not in payload["results"]]
        if missing:
            raise ProviderError(
                "FLAPI package did not return selected queries: "
                + ", ".join(missing)
            )
        rows: List[dict] = []
        for query, result in payload["results"].items():
            if selected and query not in selected:
                continue
            rows.extend(self._query_records(str(query), result))
            if len(rows) > self._MAX_ROWS:
                raise ProviderError(
                    f"FLAPI package exceeded the {self._MAX_ROWS} row safety limit"
                )
        return rows

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

    def _inspect_metadata(self, metadata: object) -> None:
        if not isinstance(metadata, dict):
            return
        trace_id = metadata.get("traceId")
        if metadata.get("isPartialSuccess"):
            self._logger.warning(
                "FLAPI package partially succeeded",
                extra={
                    "trace_id": trace_id,
                    "failed_queries": metadata.get(
                        "partialSuccessFailedQueries", []
                    ),
                },
            )
        limited = metadata.get("queriesReachedResultsLimit") or []
        if limited:
            self._logger.warning(
                "FLAPI package queries reached their result limit",
                extra={"trace_id": trace_id, "queries": limited},
            )

    def _log_failure_trace(self, response: httpx.Response) -> None:
        try:
            payload = response.json()
        except ValueError:
            return
        if not isinstance(payload, dict):
            return
        metadata = payload.get("metadata")
        trace_id = (
            metadata.get("traceId")
            if isinstance(metadata, dict) else payload.get("traceId")
        )
        if trace_id:
            self._logger.error(
                "FLAPI package request failed",
                extra={"trace_id": trace_id},
            )
