"""POST /api/query — the natural-language entry point.

Day 1: the orchestrator's agent step is stubbed, so this returns a
clarify response. The endpoint, contract, and logging are final.
"""

from fastapi import APIRouter, Depends, Request

from app.bl.query_orchestrator import QueryOrchestrator
from app.service.deps import get_orchestrator
from app.service.dto import QueryRequest, QueryResponse, gdf_to_feature_collection

router = APIRouter()


@router.post("/api/query", response_model=QueryResponse)
def run_query(
    body: QueryRequest,
    request: Request,
    orchestrator: QueryOrchestrator = Depends(get_orchestrator),
) -> QueryResponse:
    boundaries = body.boundaries.to_shapely() if body.boundaries else None
    outcome = orchestrator.run_query(body.query, boundaries)

    request.app.state.request_log.info(
        "query",
        query=body.query,
        has_boundaries=boundaries is not None,
        status=outcome.status,
        timing_ms=outcome.timing_ms,
    )
    return QueryResponse(
        status=outcome.status,
        clarify=outcome.clarify,
        plan=outcome.plan,
        features=gdf_to_feature_collection(outcome.features),
        timing_ms=outcome.timing_ms,
    )
