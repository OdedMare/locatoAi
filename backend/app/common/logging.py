"""Structured request logging to the console first, then JSON lines."""

from typing import Any

from app.common.logging_configurator import LoggingConfigurator


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
configure_logging = LoggingConfigurator.configure
