"""FastAPI accessors for dependencies wired on app.state."""

from fastapi import Request

from app.bl.query_orchestrator.query_orchestrator import QueryOrchestrator


def get_orchestrator(request: Request) -> QueryOrchestrator:
    return request.app.state.orchestrator
