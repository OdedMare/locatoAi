from pydantic import BaseModel


class AreaSummaryLayerFailure(BaseModel):
    layer_id: str
    layer_name: str
    error_type: str
    message: str
