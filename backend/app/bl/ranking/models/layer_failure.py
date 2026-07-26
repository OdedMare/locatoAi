from pydantic import BaseModel


class RankingLayerFailure(BaseModel):
    layer_id: str
    layer_name: str
    error_type: str
    message: str
