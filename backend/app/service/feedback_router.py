"""POST /api/feedback — user verdicts on agent selections.

Stores feedback in the configured PostgreSQL feedback table.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Request

from app.dal.feedback_repository import PostgresFeedbackRepository
from app.service.feedback_request import FeedbackRequest

router = APIRouter()


class FeedbackRouter:
    @staticmethod
    def submit(body: FeedbackRequest, request: Request) -> dict:
        repository: PostgresFeedbackRepository = request.app.state.feedback_repository
        repository.add(**body.model_dump(), timestamp=datetime.now(timezone.utc))
        return {"status": "ok"}


submit_feedback = FeedbackRouter.submit
router.add_api_route("/api/feedback", submit_feedback, methods=["POST"])
