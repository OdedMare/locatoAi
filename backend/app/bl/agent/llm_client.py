from typing import Dict, List, Optional, Protocol


class LLMClient(Protocol):
    """JSON-mode LLM completion implemented by the DAL LLM context.

    Returns the parsed JSON object or raises common.errors.AgentError.
    """

    def complete_json(
        self, system: str, user: str, schema: Optional[Dict] = None
    ) -> dict: ...

    def list_models(self) -> List[str]: ...
