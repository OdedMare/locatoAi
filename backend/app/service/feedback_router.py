"""POST /api/feedback — user verdicts on agent selections.

Appends JSON lines to the feedback log (see config.feedback_log_path).
Downvoted queries are the raw material for new eval cases in
scripts/eval_select_layers.py.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.common.config import get_settings

router = APIRouter()


class FeedbackRequest(BaseModel):
    query: str = Field(min_length=1)
    verdict: Literal["up", "down"]
    selected_layers: List[str] = []  # layer names shown to the user
    reasoning: str = ""
    clarify: Optional[str] = None


@router.post("/api/feedback")
def submit_feedback(body: FeedbackRequest) -> dict:
    log_path = Path(get_settings().feedback_log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    record = body.model_dump()
    record["timestamp"] = datetime.now(timezone.utc).isoformat()
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"status": "ok"}
