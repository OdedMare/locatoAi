from app.common.errors.ailocator_error import AiLocatorError


class AgentError(AiLocatorError):
    """The LLM call failed (missing key, network, unparseable output)."""
