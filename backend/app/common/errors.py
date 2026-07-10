"""Domain exceptions. The service tier maps these to HTTP responses."""


class AiLocatorError(Exception):
    """Base class for all domain errors."""


class LayerNotFoundError(AiLocatorError):
    def __init__(self, layer_id: str):
        self.layer_id = layer_id
        super().__init__(f"Layer not found in catalog: {layer_id}")


class PlanValidationError(AiLocatorError):
    """The plan is structurally invalid (bad refs, cycles, unknown layers...)."""


class ProviderError(AiLocatorError):
    """A provider failed to serve schema or features."""


class ExecutionError(AiLocatorError):
    """A plan step failed at execution time (bad field, empty input...)."""


class AgentError(AiLocatorError):
    """The LLM call failed (missing key, network, unparseable output)."""
