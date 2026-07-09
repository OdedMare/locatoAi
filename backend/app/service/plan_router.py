"""POST /api/execute-plan — debug endpoint: run a hand-written plan.

This is Milestone 1: plan-in → GeoJSON-out with no AI. It stays useful
forever as the way to test the executor in isolation.
"""

from fastapi import APIRouter, Depends, Request

from app.bl.query_orchestrator import QueryOrchestrator
from app.service.deps import get_orchestrator
from app.service.dto import (
    ExecutePlanRequest,
    QueryResponse,
    gdf_to_feature_collection,
)

router = APIRouter()


@router.post("/api/execute-plan", response_model=QueryResponse)
def execute_plan(
    body: ExecutePlanRequest,
    request: Request,
    orchestrator: QueryOrchestrator = Depends(get_orchestrator),
) -> QueryResponse:
    boundaries = body.boundaries.to_shapely() if body.boundaries else None
    outcome = orchestrator.execute_plan(body.plan, boundaries)

    result_count = len(outcome.features) if outcome.features is not None else 0
    request.app.state.request_log.info(
        "execute_plan",
        plan_output=body.plan.output,
        has_boundaries=boundaries is not None,
        status=outcome.status,
        result_count=result_count,
        timing_ms=outcome.timing_ms,
    )
    return QueryResponse(
        status=outcome.status,
        plan=outcome.plan,
        features=gdf_to_feature_collection(outcome.features),
        timing_ms=outcome.timing_ms,
    )
