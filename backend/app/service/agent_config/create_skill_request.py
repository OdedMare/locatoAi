from pydantic import BaseModel, Field


class CreateAgentSkillRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=100000)
