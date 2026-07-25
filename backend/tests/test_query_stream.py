import json
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.bl.query_orchestrator.query_orchestrator import QueryOrchestrator
from app.bl.query_orchestrator.query_outcome import QueryOutcome
from app.service.dependencies import get_orchestrator
from app.service.query.router import router


class StreamingOrchestrator:
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


def test_query_stream_sends_trace_before_final_result():
    app = FastAPI()
    app.state.request_log = Mock()
    app.include_router(router)
    app.dependency_overrides[get_orchestrator] = lambda: StreamingOrchestrator()
    response = TestClient(app).post(
        "/api/query/stream",
        headers={"X-Request-ID": "stream-test"},
        json={
            "query": "מצא ישויות",
            "boundaries": {
                "type": "MultiPolygon",
                "coordinates": [[[[34.0, 32.0], [34.1, 32.0], [34.1, 32.1],
                                   [34.0, 32.1], [34.0, 32.0]]]],
            },
        },
    )

    frames = [
        (block.splitlines()[0], json.loads(block.splitlines()[1][6:]))
        for block in response.text.strip().split("\n\n")
    ]
    assert response.headers["content-type"].startswith("text/event-stream")
    assert [event for event, _ in frames] == [
        "event: trace", "event: trace", "event: result",
    ]
    assert frames[1][1]["output_count"] == 2
    assert frames[-1][1]["request_id"] == "stream-test"
