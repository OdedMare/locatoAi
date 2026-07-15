"""Structured request logging to the console first, then JSON lines."""

import logging
from pathlib import Path
from typing import Any

import structlog

_REQUEST_LOGGER_NAME = "ailocator.requests"
_REQUEST_CONSOLE_LOGGER_NAME = "ailocator.requests.console"


class ConsoleFirstLogger:
    """Write every structured event to the console before the JSONL file."""

    def __init__(self, console: Any, persistent: Any):
        self._console = console
        self._persistent = persistent

    def bind(self, **context: Any) -> "ConsoleFirstLogger":
        return ConsoleFirstLogger(
            self._console.bind(**context), self._persistent.bind(**context)
        )

    def info(self, event: str, **context: Any) -> None:
        self._write("info", event, context)

    def warning(self, event: str, **context: Any) -> None:
        self._write("warning", event, context)

    def error(self, event: str, **context: Any) -> None:
        self._write("error", event, context)

    def exception(self, event: str, **context: Any) -> None:
        context.setdefault("exc_info", True)
        self._write("error", event, context)

    def _write(self, level: str, event: str, context: Any) -> None:
        getattr(self._console, level)(event, **context)
        getattr(self._persistent, level)(event, **context)


def _replace_handlers(name: str, handler: logging.Handler) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers = [handler]
    logger.propagate = False
    return logger


def configure_logging(request_log_path: str) -> ConsoleFirstLogger:
    """Configure ordered console and persistent structured request logging."""
    log_file = Path(request_log_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter("%(message)s")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_logger = _replace_handlers(_REQUEST_LOGGER_NAME, file_handler)
    console_logger = _replace_handlers(
        _REQUEST_CONSOLE_LOGGER_NAME, console_handler
    )

    _replace_handlers("app", console_handler)

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
    )
    return ConsoleFirstLogger(
        structlog.wrap_logger(console_logger),
        structlog.wrap_logger(file_logger),
    )
