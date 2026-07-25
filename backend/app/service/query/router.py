"""POST /api/query — natural-language query entry point."""

import re
from uuid import uuid4

from fastapi import APIRouter, Depends, Request

from app.bl.query_orchestrator.query_orchestrator import QueryOrchestrator
from app.service.dependencies import get_orchestrator
from app.service.query.event_sink import QueryEventSink
from app.service.query.request import QueryRequest
from app.service.query.response import QueryResponse

router = APIRouter()
_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def run_query(
    body: QueryRequest,
    request: Request,
    orchestrator: QueryOrchestrator = Depends(get_orchestrator),
) -> QueryResponse:
    boundaries = body.boundaries.to_shapely()
    request_id, logger = _start(request, body.query, boundaries)
    outcome = _execute(
        orchestrator,
        body.query,
        boundaries,
        QueryEventSink(request, logger),
        logger,
    )
    return _complete(request, body.query, request_id, logger, outcome)


def _start(request: Request, query: str, boundaries):
    request_id = _request_id(request)
    request.state.request_id = request_id
    request.state.pipeline_trace = []
    logger = request.app.state.request_log.bind(request_id=request_id)
    logger.info("query_started", query=query, **_boundary_context(boundaries))
    return request_id, logger


def _execute(orchestrator, query, boundaries, event_sink, logger):
    try:
        return orchestrator.run_query(query, boundaries, event_sink=event_sink)
    except Exception as exc:
        logger.error(
            "query_failed",
            query=query,
            error_type=type(exc).__name__,
            error=str(exc),
            exc_info=True,
        )
        raise


def _complete(request, query, request_id, logger, outcome):
    outcome.pipeline_trace = request.state.pipeline_trace
    logger.info("query_completed", query=query, **_outcome_context(outcome))
    response = QueryResponse.from_outcome(outcome)
    response.request_id = request_id
    return response


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


def _result_count(outcome) -> int:
    if outcome.features is not None:
        return len(outcome.features)
    return outcome.scalar_result or 0


router.add_api_route(
    "/api/query", run_query, methods=["POST"], response_model=QueryResponse
)
