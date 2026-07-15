from app.common.errors.ailocator_error import AiLocatorError


class ProviderError(AiLocatorError):
    """A provider failed to serve schema or features."""
