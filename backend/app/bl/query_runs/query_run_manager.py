"""Small in-memory job runner for the UI's asynchronous geo queries."""

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from uuid import uuid4

from app.bl.query_runs.query_run import QueryRun
from app.common.errors.ailocator_error import AiLocatorError

_RETENTION = timedelta(minutes=10)


class QueryRunManager:
    def __init__(self, orchestrator, logger, max_workers: int = 4) -> None:
        self._orchestrator = orchestrator
        self._logger = logger
        self._runs: Dict[str, QueryRun] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="geo-query",
        )

    def submit(self, run_id: str, query: str, boundaries) -> QueryRun:
        now = datetime.now(timezone.utc)
        with self._lock:
            self._purge(now)
            actual_id = run_id if run_id not in self._runs else uuid4().hex
            self._runs[actual_id] = QueryRun(
                actual_id, query, "queued", now, now,
            )
        self._pool.submit(self._execute, actual_id, boundaries)
        return self.get(actual_id)

    def get(self, run_id: str) -> Optional[QueryRun]:
        with self._lock:
            self._purge(datetime.now(timezone.utc))
            run = self._runs.get(run_id)
            if run is None:
                return None
            return replace(run, pipeline_trace=list(run.pipeline_trace))

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False)

    def _execute(self, run_id: str, boundaries) -> None:
        run = self._set_status(run_id, "running")
        logger = self._logger.bind(request_id=run_id)
        logger.info("query_started", query=run.query, async_run=True)
        try:
            outcome = self._orchestrator.run_query(
                run.query, boundaries,
                event_sink=lambda event: self._event(run_id, event, logger),
            )
        except Exception as exc:
            self._fail(run_id, exc, logger)
            return
        self._complete(run_id, outcome, logger)

    def _set_status(self, run_id: str, status: str) -> QueryRun:
        with self._lock:
            run = self._runs[run_id]
            run.status = status
            run.updated_at = datetime.now(timezone.utc)
            return replace(run, pipeline_trace=list(run.pipeline_trace))

    def _event(self, run_id: str, event: dict, logger) -> None:
        with self._lock:
            run = self._runs[run_id]
            run.pipeline_trace.append(event)
            run.updated_at = datetime.now(timezone.utc)
        logger.info("query_pipeline", **event)

    def _complete(self, run_id: str, outcome, logger) -> None:
        with self._lock:
            run = self._runs[run_id]
            outcome.pipeline_trace = list(run.pipeline_trace)
            run.outcome = outcome
            run.status = "completed"
            run.updated_at = datetime.now(timezone.utc)
        logger.info("query_completed", status=outcome.status, async_run=True)

    def _fail(self, run_id: str, exc: Exception, logger) -> None:
        with self._lock:
            run = self._runs[run_id]
            run.status = "failed"
            run.error_type = type(exc).__name__
            run.error = (
                str(exc) if isinstance(exc, AiLocatorError)
                else "Internal server error"
            )
            run.updated_at = datetime.now(timezone.utc)
        logger.error(
            "query_failed", error_type=type(exc).__name__, error=str(exc),
            exc_info=True,
        )

    def _purge(self, now: datetime) -> None:
        expired = [
            run_id for run_id, run in self._runs.items()
            if run.status in ("completed", "failed")
            and now - run.updated_at > _RETENTION
        ]
        for run_id in expired:
            self._runs.pop(run_id, None)
