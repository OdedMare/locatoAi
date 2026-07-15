"""POST /api/execute-plan — debug endpoint: run a hand-written plan.

Plan-in → GeoJSON-out with no AI. It stays useful forever as the way to
test the executor in isolation.
"""

from fastapi import APIRouter, Depends, Request

from app.bl.query_orchestrator import QueryOrchestrator
from app.service.deps import get_orchestrator
from app.service.dto.execute_plan_request import ExecutePlanRequest
from app.service.dto.query_response import QueryResponse

router = APIRouter()


@router.post("/api/execute-plan", response_model=QueryResponse)
def execute_plan(
    body: ExecutePlanRequest,
    request: Request,
    orchestrator: QueryOrchestrator = Depends(get_orchestrator),
) -> QueryResponse:
    boundaries = body.boundaries.to_shapely()
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
    return QueryResponse.from_outcome(outcome)
