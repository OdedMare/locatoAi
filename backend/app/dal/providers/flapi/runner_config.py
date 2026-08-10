"""Timeout and credential compatibility for the internal FLUNKS runtime."""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError

from app.common.errors.provider_error import ProviderError
from app.common.flapi_workers import record_abandoned_worker

_DEFAULT_TIMEOUT_SECONDS = 120
_TLS_FIELDS = ("verify_tls", "verify", "verify_ssl")
_logger = logging.getLogger(__name__)
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="flunks")


def resolve_timeout(settings) -> int:
    configured = getattr(
        settings, "package_timeout_seconds", _DEFAULT_TIMEOUT_SECONDS,
    )
    return max(1, int(configured))


def run_bounded(runner, timeout: float, package_key: str):
    """Wait at most ``timeout`` seconds for an uncancellable FLUNKS call."""
    started = time.time()
    future = _pool.submit(runner.run)
    try:
        return future.result(timeout=timeout)
    except FutureTimeoutError:
        _record_abandoned(package_key, timeout, future)
        raise ProviderError(
            "FLAPI package timed out after %s seconds: %s"
            % (timeout, package_key)
        )
    finally:
        _logger.debug(
            "FLAPI bounded run finished waiting package=%s elapsed=%.2fs",
            package_key, time.time() - started,
        )


def _record_abandoned(package_key: str, timeout: float, future) -> None:
    if future.cancel():
        _logger.error(
            "FLAPI package TIMEOUT id=%s after=%ss before worker start",
            package_key, timeout,
        )
        return
    total = record_abandoned_worker()
    _logger.error(
        "FLAPI package TIMEOUT id=%s after=%ss abandoned_total=%d threads=%d",
        package_key, timeout, total, threading.active_count(),
    )
    future.add_done_callback(
        lambda done: _logger.warning(
            "FLAPI abandoned worker finished id=%s cancelled=%s",
            package_key, done.cancelled(),
        )
    )


def build_flapi_config(config_class, settings):
    values = {
        "username": settings.flapi_username,
        "token": settings.cubes_token,
    }
    tls_field = next(
        (field for field in _TLS_FIELDS if _accepts(config_class, field)), None,
    )
    if tls_field:
        values[tls_field] = settings.cubes_verify_tls
    elif not settings.cubes_verify_tls:
        _logger.warning(
            "cubes_verify_tls=False ignored: FLUNKS exposes no TLS field"
        )
    return config_class(**values)


def _accepts(config_class, field: str) -> bool:
    for attribute in ("model_fields", "__fields__", "__annotations__"):
        fields = getattr(config_class, attribute, None)
        if isinstance(fields, dict):
            return field in fields
    return False
