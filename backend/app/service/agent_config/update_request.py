from pydantic import BaseModel, Field


class UpdateAgentContentRequest(BaseModel):
    content: str = Field(min_length=1, max_length=100000)
