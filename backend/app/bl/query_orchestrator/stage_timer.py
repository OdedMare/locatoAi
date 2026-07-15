import time
from typing import Dict


class StageTimer:
    """Collects per-stage elapsed milliseconds."""

    def __init__(self) -> None:
        self.timing: Dict[str, int] = {}
        self._started = time.perf_counter()

    def mark(self, stage: str) -> None:
        now = time.perf_counter()
        self.timing[stage] = int((now - self._started) * 1000)
        self._started = now
