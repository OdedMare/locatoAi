"""Configure console-first structured request logging."""

import logging
from pathlib import Path

import structlog

from app.common.logging.console_logger import ConsoleFirstLogger

_REQUEST_LOGGER = "ailocator.requests"
_CONSOLE_LOGGER = "ailocator.requests.console"


def configure_logging(request_log_path: str) -> ConsoleFirstLogger:
    file_handler, console_handler = _handlers(request_log_path)
    file_logger = _replace_handlers(_REQUEST_LOGGER, file_handler)
    console_logger = _replace_handlers(_CONSOLE_LOGGER, console_handler)
    _replace_handlers("app", console_handler)
    _configure_structlog()
    return ConsoleFirstLogger(
        structlog.wrap_logger(console_logger),
        structlog.wrap_logger(file_logger),
    )


def _handlers(request_log_path: str):
    log_file = Path(request_log_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(message)s")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    return file_handler, console_handler


def _replace_handlers(name: str, handler: logging.Handler) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers = [handler]
    logger.propagate = False
    return logger


def _configure_structlog() -> None:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
    )
