"""Structured request logging → JSON-lines file (Elastic comes in v0.2)."""

import logging
from pathlib import Path

import structlog


def configure_logging(request_log_path: str) -> structlog.stdlib.BoundLogger:
    """Configure structlog to append JSON lines to the request log file."""
    log_file = Path(request_log_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))

    file_logger = logging.getLogger("ailocator.requests")
    file_logger.setLevel(logging.INFO)
    file_logger.handlers = [handler]
    file_logger.propagate = False

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
    )
    return structlog.wrap_logger(file_logger)
