"""POST /api/feedback — user verdicts on agent selections.

Stores feedback in the configured PostgreSQL feedback table.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Request

from app.service.feedback.request import FeedbackRequest

router = APIRouter()


def submit_feedback(body: FeedbackRequest, request: Request) -> dict:
    repository = request.app.state.feedback_repository
    repository.add(**body.model_dump(), timestamp=datetime.now(timezone.utc))
    return {"status": "ok"}


router.add_api_route("/api/feedback", submit_feedback, methods=["POST"])
