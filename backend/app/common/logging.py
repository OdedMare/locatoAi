"""Structured request logging to JSON lines and the server console."""

import logging
from pathlib import Path

import structlog

_REQUEST_LOGGER_NAME = "ailocator.requests"


def configure_logging(request_log_path: str) -> structlog.stdlib.BoundLogger:
    """Configure structlog to append JSON lines to the request log file."""
    log_file = Path(request_log_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter("%(message)s")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_logger = logging.getLogger(_REQUEST_LOGGER_NAME)
    file_logger.setLevel(logging.INFO)
    file_logger.handlers = [file_handler, console_handler]
    file_logger.propagate = False

    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.INFO)
    app_logger.handlers = [console_handler]
    app_logger.propagate = False

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
    )
    return structlog.wrap_logger(file_logger)
