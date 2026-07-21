from typing import List, Optional

from pydantic import BaseModel

from app.service.agent.selected_layer import SelectedLayer


class SelectLayersResponse(BaseModel):
    layers: List[SelectedLayer]
    clarify: Optional[str] = None
    reasoning: str = ""
    timing_ms: int
    token_usage: Optional[dict] = None
