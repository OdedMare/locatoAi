"""Process-wide accounting for FLUNKS calls that outlive their timeout."""

import threading

_abandoned = 0
_lock = threading.Lock()


def record_abandoned_worker() -> int:
    global _abandoned
    with _lock:
        _abandoned += 1
        return _abandoned


def abandoned_workers() -> int:
    with _lock:
        return _abandoned
