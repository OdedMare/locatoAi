from typing import List

from pydantic import BaseModel

from app.service.catalog.remote_mqs_layer_response import RemoteMqsLayerResponse


class RemoteMqsLayersResponse(BaseModel):
    layers: List[RemoteMqsLayerResponse]
    count: int
    skipped: int
