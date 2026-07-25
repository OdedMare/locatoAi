from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.bl.query_orchestrator.query_orchestrator import QueryOrchestrator
from app.bl.query_orchestrator.query_outcome import QueryOutcome
from app.service.dependencies import get_orchestrator
from app.service.query.router import router

BOUNDARIES = {
    "type": "MultiPolygon",
    "coordinates": [[[[34.0, 32.0], [34.1, 32.0], [34.1, 32.1],
                       [34.0, 32.1], [34.0, 32.0]]]],
}


class RecordingOrchestrator:
    @staticmethod
    def run_query(query, boundaries, event_sink=None):
        event_sink({
            "stage": "execute_step", "status": "started",
            "step_id": "load_entities", "operation": "load",
        })
        event_sink({
            "stage": "execute_step", "status": "completed",
            "step_id": "load_entities", "operation": "load", "output_count": 2,
        })
        return QueryOutcome(status="ok", scalar_result=2)


def test_run_stage_emits_start_and_completion():
    events = []

    result = QueryOrchestrator._run_stage("execution", lambda: 2, events.append)

    assert result == 2
    assert events == [
        {"stage": "execution", "status": "started"},
        {"stage": "execution", "status": "completed"},
    ]


def query_app():
    app = FastAPI()
    app.state.request_log = Mock()
    app.include_router(router)
    app.dependency_overrides[get_orchestrator] = lambda: RecordingOrchestrator()
    return app


def test_query_response_includes_pipeline_trace():
    response = TestClient(query_app()).post(
        "/api/query",
        headers={"X-Request-ID": "query-test"},
        json={"query": "מצא ישויות", "boundaries": BOUNDARIES},
    )

    body = response.json()
    assert response.headers["content-type"].startswith("application/json")
    assert [event["status"] for event in body["pipeline_trace"]] == [
        "started", "completed",
    ]
    assert body["pipeline_trace"][1]["output_count"] == 2
    assert body["request_id"] == "query-test"
