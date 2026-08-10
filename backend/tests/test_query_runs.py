import time
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.bl.query_orchestrator.query_outcome import QueryOutcome
from app.bl.query_runs.query_run_manager import QueryRunManager
from app.service.query.router import router


BOUNDARIES = {
    "type": "MultiPolygon",
    "coordinates": [[[[34.7, 32.0], [34.9, 32.0], [34.9, 32.2],
                       [34.7, 32.2], [34.7, 32.0]]]],
}


def query_app(action):
    logger = MagicMock()
    logger.bind.return_value = logger
    orchestrator = MagicMock()
    orchestrator.run_query.side_effect = action
    app = FastAPI()
    app.state.query_runs = QueryRunManager(orchestrator, logger, max_workers=1)
    app.add_event_handler("shutdown", app.state.query_runs.shutdown)
    app.include_router(router)
    return app


def completed_run(client, run_id):
    for _ in range(100):
        response = client.get("/api/query-runs/%s" % run_id)
        if response.json()["status"] not in ("queued", "running"):
            return response
        time.sleep(0.01)
    raise AssertionError("query run did not finish")


def test_query_run_polls_live_trace_and_final_response():
    def execute(_query, _boundaries, event_sink=None):
        event_sink({"stage": "layer_selection", "status": "started"})
        return QueryOutcome(status="clarify", clarify="צריך פירוט")

    app = query_app(execute)
    with TestClient(app) as client:
        started = client.post(
            "/api/query-runs", json={"query": "איפה?", "boundaries": BOUNDARIES},
            headers={"X-Request-ID": "query-run-1"},
        )
        finished = completed_run(client, started.json()["id"])

    assert started.status_code == 202
    assert finished.json()["status"] == "completed"
    assert finished.json()["response"]["clarify"] == "צריך פירוט"
    assert finished.json()["pipeline_trace"] == [
        {"stage": "layer_selection", "status": "started"}
    ]


def test_query_run_reports_background_failure():
    def fail(_query, _boundaries, event_sink=None):
        event_sink({"stage": "execution", "status": "failed"})
        raise RuntimeError("provider exploded")

    app = query_app(fail)
    with TestClient(app) as client:
        started = client.post(
            "/api/query-runs", json={"query": "איפה?", "boundaries": BOUNDARIES},
        )
        finished = completed_run(client, started.json()["id"])

    body = finished.json()
    assert body["status"] == "failed"
    assert body["error_type"] == "RuntimeError"
    assert body["error"] == "Internal server error"
