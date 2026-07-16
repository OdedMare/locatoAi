"""POST /api/query — the natural-language entry point.

Current stage: layer selection is live; plan building is next, so a
successful selection returns a clarify naming the chosen layers.
"""

import re
from uuid import uuid4

from fastapi import APIRouter, Depends, Request

from app.bl.query_orchestrator.query_orchestrator import QueryOrchestrator
from app.service.deps import get_orchestrator
from app.service.dto.query_request import QueryRequest
from app.service.dto.query_response import QueryResponse

router = APIRouter()
_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def _request_id(request: Request) -> str:
    supplied = request.headers.get("X-Request-ID", "")
    return supplied if _REQUEST_ID.fullmatch(supplied) else uuid4().hex


def _boundary_context(boundaries) -> dict:
    return {
        "has_boundaries": boundaries is not None,
        "boundary_type": boundaries.geom_type if boundaries is not None else None,
        "boundary_bounds": list(boundaries.bounds) if boundaries is not None else None,
        "boundary_valid": boundaries.is_valid if boundaries is not None else None,
    }


def _result_count(outcome) -> int:
    if outcome.features is not None:
        return len(outcome.features)
    return outcome.scalar_result or 0


def _outcome_context(outcome) -> dict:
    return {
        "status": outcome.status,
        "clarify": outcome.clarify,
        "selected_layer_ids": [layer.id for layer in outcome.selected_layers],
        "selected_layer_names": [layer.name for layer in outcome.selected_layers],
        "selection_reasoning": outcome.reasoning,
        "plan": outcome.plan.model_dump(by_alias=True) if outcome.plan else None,
        "tool_calls": outcome.tool_calls,
        "pipeline_trace": outcome.pipeline_trace,
        "timing_ms": outcome.timing_ms,
        "token_usage": outcome.token_usage,
        "result_count": _result_count(outcome),
    }


@router.post("/api/query", response_model=QueryResponse)
def run_query(
    body: QueryRequest,
    request: Request,
    orchestrator: QueryOrchestrator = Depends(get_orchestrator),
) -> QueryResponse:
    boundaries = body.boundaries.to_shapely()
    request_id = _request_id(request)
    request.state.request_id = request_id
    request.state.pipeline_trace = []
    log = request.app.state.request_log.bind(request_id=request_id)
    log.info("query_started", query=body.query, **_boundary_context(boundaries))

    def emit(event: dict) -> None:
        request.state.pipeline_trace.append(event)
        log.info("query_pipeline", **event)

    try:
        outcome = orchestrator.run_query(body.query, boundaries, event_sink=emit)
    except Exception as exc:
        log.error(
            "query_failed", query=body.query, error_type=type(exc).__name__,
            error=str(exc), exc_info=True,
        )
        raise

    outcome.pipeline_trace = request.state.pipeline_trace
    log.info("query_completed", query=body.query, **_outcome_context(outcome))
    response = QueryResponse.from_outcome(outcome)
    response.request_id = request_id
    return response
