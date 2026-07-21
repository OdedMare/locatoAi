"""Configure console-first structured request logging."""

import logging
from pathlib import Path

import structlog

from app.common.logging.console_logger import ConsoleFirstLogger


class LoggingConfigurator:
    REQUEST_LOGGER = "ailocator.requests"
    CONSOLE_LOGGER = "ailocator.requests.console"

    @classmethod
    def configure(cls, request_log_path: str) -> ConsoleFirstLogger:
        file_handler, console_handler = cls._handlers(request_log_path)
        file_logger = cls._replace_handlers(cls.REQUEST_LOGGER, file_handler)
        console_logger = cls._replace_handlers(cls.CONSOLE_LOGGER, console_handler)
        cls._replace_handlers("app", console_handler)
        cls._configure_structlog()
        return ConsoleFirstLogger(
            structlog.wrap_logger(console_logger),
            structlog.wrap_logger(file_logger),
        )


    @staticmethod
    def _handlers(request_log_path: str):
        log_file = Path(request_log_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        formatter = logging.Formatter("%(message)s")
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        return file_handler, console_handler

    @staticmethod
    def _replace_handlers(name: str, handler: logging.Handler) -> logging.Logger:
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        logger.handlers = [handler]
        logger.propagate = False
        return logger

    @staticmethod
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


configure_logging = LoggingConfigurator.configure
