"""POST /api/query — the natural-language entry point.

Current stage: layer selection is live; plan building is next, so a
successful selection returns a clarify naming the chosen layers.
"""

from fastapi import APIRouter, Depends, Request

from app.bl.query_orchestrator import QueryOrchestrator
from app.service.deps import get_orchestrator
from app.service.dto.query_request import QueryRequest
from app.service.dto.query_response import QueryResponse

router = APIRouter()


@router.post("/api/query", response_model=QueryResponse)
def run_query(
    body: QueryRequest,
    request: Request,
    orchestrator: QueryOrchestrator = Depends(get_orchestrator),
) -> QueryResponse:
    boundaries = body.boundaries.to_shapely()
    outcome = orchestrator.run_query(body.query, boundaries)

    request.app.state.request_log.info(
        "query",
        query=body.query,
        has_boundaries=boundaries is not None,
        status=outcome.status,
        selected=[layer.name for layer in outcome.selected_layers],
        timing_ms=outcome.timing_ms,
    )
    return QueryResponse.from_outcome(outcome)
