"""FastAPI exception handler with structured diagnostics."""

import logging

from fastapi.responses import JSONResponse


class ErrorHandler:
    def __init__(self, status_code: int) -> None:
        self._status_code = status_code
        self._logger = logging.getLogger("ailocator")

    async def __call__(self, request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        context = self._context(request, exc, request_id)
        request_logger = getattr(request.app.state, "request_log", None)
        if request_logger is not None:
            request_logger.error("request_failed", **context, exc_info=True)
        else:
            self._logger.exception("request_failed %s", context)
        response = JSONResponse(
            status_code=self._status_code,
            content=self._content(request, exc, request_id),
        )
        if request_id:
            response.headers["X-Request-ID"] = request_id
        return response

    def _context(self, request, exc, request_id) -> dict:
        return {
            "method": request.method,
            "path": request.url.path,
            "status_code": self._status_code,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "request_id": request_id,
        }

    def _content(self, request, exc, request_id) -> dict:
        detail = str(exc) if self._status_code != 500 else "Internal server error"
        return {
            "status": "error",
            "request_id": request_id,
            "detail": detail,
            "error_type": type(exc).__name__,
            "pipeline_trace": getattr(request.state, "pipeline_trace", []),
        }
