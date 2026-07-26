"""Agent-selection feedback request."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    query: str = Field(min_length=1)
    verdict: Literal["up", "down"]
    selected_layers: List[str] = Field(default_factory=list)
    reasoning: str = ""
    clarify: Optional[str] = None
