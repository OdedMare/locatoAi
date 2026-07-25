"""Event sink for one query request."""


class QueryEventSink:
    def __init__(self, request, logger) -> None:
        self._request = request
        self._logger = logger

    def __call__(self, event: dict) -> None:
        self._request.state.pipeline_trace.append(event)
        self._logger.info("query_pipeline", **event)
