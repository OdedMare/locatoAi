"""POST /api/ranking — scored, evidence-backed ranking for one polygon."""

from fastapi import APIRouter, HTTPException, Request

from app.bl.ranking.models.result import RankingResult
from app.service.ranking.request import RankingRequest

router = APIRouter()


def rank_area(body: RankingRequest, request: Request) -> RankingResult:
    boundaries = _boundaries(body)
    result = request.app.state.ranking.rank(
        boundaries,
        subject_layer_id=body.subject_layer_id,
        window_start=body.from_,
        window_end=body.to,
        limit=body.limit,
    )
    _log(request, result)
    return result


def _boundaries(body):
    try:
        boundaries = body.boundaries.to_shapely()
    except (IndexError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail="Ranking boundaries are malformed"
        ) from exc
    if boundaries.is_empty or not boundaries.is_valid:
        raise HTTPException(status_code=422, detail="Ranking boundaries must be valid")
    return boundaries


def _log(request, result):
    request.app.state.request_log.info(
        "ranking_completed",
        subject_layer_id=result.subject_layer_id,
        subject_feature_count=result.subject_feature_count,
        applied_rule_count=result.applied_rule_count,
        successful_rule_count=result.successful_rule_count,
        ranked_feature_count=len(result.features),
        failure_count=len(result.failures),
    )


router.add_api_route(
    "/api/ranking",
    rank_area,
    methods=["POST"],
    response_model=RankingResult,
)
