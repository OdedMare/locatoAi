from pydantic import BaseModel


class AgentContentResponse(BaseModel):
    id: str
    title: str
    kind: str
    content: str
    is_custom: bool
    is_overridden: bool
