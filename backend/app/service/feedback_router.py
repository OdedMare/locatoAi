"""POST /api/feedback — user verdicts on agent selections.

Stores feedback in the configured PostgreSQL feedback table.
"""

from datetime import datetime, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.dal.feedback_repository import PostgresFeedbackRepository

router = APIRouter()


class FeedbackRequest(BaseModel):
    query: str = Field(min_length=1)
    verdict: Literal["up", "down"]
    selected_layers: List[str] = Field(default_factory=list)  # layer names shown
    reasoning: str = ""
    clarify: Optional[str] = None


@router.post("/api/feedback")
def submit_feedback(body: FeedbackRequest, request: Request) -> dict:
    repository: PostgresFeedbackRepository = request.app.state.feedback_repository
    repository.add(**body.model_dump(), timestamp=datetime.now(timezone.utc))
    return {"status": "ok"}
