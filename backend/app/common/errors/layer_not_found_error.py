from app.common.errors.ailocator_error import AiLocatorError


class LayerNotFoundError(AiLocatorError):
    def __init__(self, layer_id: str):
        self.layer_id = layer_id
        super().__init__(f"Layer not found in catalog: {layer_id}")
