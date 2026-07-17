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


class AgentRouter:
    @staticmethod
    def select_layers(
        body: SelectLayersRequest, request: Request
    ) -> SelectLayersResponse:
        selector: LayerSelector = request.app.state.layer_selector
        started = time.perf_counter()
        selection = selector.select(body.query)
        timing_ms = int((time.perf_counter() - started) * 1000)
        AgentRouter._log(request, body.query, selection, timing_ms)
        return SelectLayersResponse(
            layers=[SelectedLayer(id=item.id, name=item.name, tags=item.tags)
                    for item in selection.layers],
            clarify=selection.clarify,
            reasoning=selection.reasoning,
            timing_ms=timing_ms,
        )

    @staticmethod
    def _log(request, query, selection, timing_ms) -> None:
        request.app.state.request_log.info(
            "select_layers", query=query,
            selected=[layer.name for layer in selection.layers],
            clarify=selection.clarify, timing_ms=timing_ms,
            token_usage=selection.token_usage,
        )


select_layers = AgentRouter.select_layers
router.add_api_route(
    "/api/select-layers", select_layers,
    methods=["POST"], response_model=SelectLayersResponse,
)
