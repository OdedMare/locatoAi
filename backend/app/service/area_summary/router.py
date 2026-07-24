"""POST /api/area-summary — evidence-backed facts for one polygon."""

from fastapi import APIRouter, HTTPException, Request

from app.bl.area_summary.models.result import AreaSummaryResult
from app.service.area_summary.request import AreaSummaryRequest

router = APIRouter()


class AreaSummaryRouter:
    @staticmethod
    def summarize(
        body: AreaSummaryRequest, request: Request,
    ) -> AreaSummaryResult:
        boundaries = AreaSummaryRouter._boundaries(body)
        result = request.app.state.area_summary.summarize(
            boundaries,
            window_start=body.from_,
            window_end=body.to,
            encounter_distance_m=body.encounter_distance_m,
            encounter_time_tolerance_minutes=(
                body.encounter_time_tolerance_minutes
            ),
        )
        AreaSummaryRouter._log(request, result)
        return result

    @staticmethod
    def _validate_boundaries(boundaries):
        if boundaries.is_empty or not boundaries.is_valid:
            raise HTTPException(
                status_code=422, detail="Area summary boundaries must be valid"
            )

    @classmethod
    def _boundaries(cls, body):
        try:
            boundaries = body.boundaries.to_shapely()
        except (IndexError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422, detail="Area summary boundaries are malformed"
            ) from exc
        cls._validate_boundaries(boundaries)
        return boundaries

    @staticmethod
    def _log(request, result):
        request.app.state.request_log.info(
            "area_summary_completed",
            queried_layer_count=result.queried_layer_count,
            successful_layer_count=result.successful_layer_count,
            fact_count=len(result.facts),
            failure_count=len(result.failures),
        )


summarize_area = AreaSummaryRouter.summarize
router.add_api_route(
    "/api/area-summary", summarize_area,
    methods=["POST"], response_model=AreaSummaryResult,
)
