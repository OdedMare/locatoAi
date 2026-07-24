from typing import List

from pydantic import BaseModel

from app.service.agent_config.content_response import AgentContentResponse


class AgentConfigResponse(BaseModel):
    prompts: List[AgentContentResponse]
    skills: List[AgentContentResponse]
