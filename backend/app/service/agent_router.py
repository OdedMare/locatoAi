"""POST /api/select-layers — debug endpoint for agent call 1.

Lets you verify the model extracts the right layers from the PG catalog
for a given query, without running the rest of the pipeline.
"""

import time
from typing import List, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.bl.agent.select_layers import LayerSelector

router = APIRouter()


class SelectLayersRequest(BaseModel):
    query: str = Field(min_length=1)


class SelectedLayer(BaseModel):
    id: str
    name: str
    tags: List[str]


class SelectLayersResponse(BaseModel):
    layers: List[SelectedLayer]
    clarify: Optional[str] = None
    reasoning: str = ""
    timing_ms: int
    token_usage: Optional[dict] = None


@router.post("/api/select-layers", response_model=SelectLayersResponse)
def select_layers(body: SelectLayersRequest, request: Request) -> SelectLayersResponse:
    selector: LayerSelector = request.app.state.layer_selector

    started = time.perf_counter()
    selection = selector.select(body.query)
    timing_ms = int((time.perf_counter() - started) * 1000)

    request.app.state.request_log.info(
        "select_layers",
        query=body.query,
        selected=[layer.name for layer in selection.layers],
        clarify=selection.clarify,
        timing_ms=timing_ms,
        token_usage=selection.token_usage,
    )
    return SelectLayersResponse(
        layers=[
            SelectedLayer(id=l.id, name=l.name, tags=l.tags) for l in selection.layers
        ],
        clarify=selection.clarify,
        reasoning=selection.reasoning,
        timing_ms=timing_ms,
    )
