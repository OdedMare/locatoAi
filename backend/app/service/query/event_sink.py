"""Event sink for one query request."""

from typing import Callable, Optional


class QueryEventSink:
    def __init__(
        self, request, logger,
        forward: Optional[Callable[[dict], None]] = None,
    ) -> None:
        self._request = request
        self._logger = logger
        self._forward = forward

    def __call__(self, event: dict) -> None:
        self._request.state.pipeline_trace.append(event)
        self._logger.info("query_pipeline", **event)
        if self._forward is not None:
            self._forward(event)
