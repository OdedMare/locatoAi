"""POST /api/select-layers — debug endpoint for agent call 1.

Lets you verify the model extracts the right layers from the PG catalog
for a given query, without running the rest of the pipeline.
"""

import time

from fastapi import APIRouter, Request

from app.bl.agent.select_layers.layer_selector import LayerSelector
from app.service.agent_dto.select_layers_request import SelectLayersRequest
from app.service.agent_dto.select_layers_response import SelectLayersResponse
from app.service.agent_dto.selected_layer import SelectedLayer

router = APIRouter()


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
