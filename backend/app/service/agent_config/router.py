"""Browse and edit the model-facing agent configuration."""

from fastapi import APIRouter, HTTPException, Request

from app.service.agent_config.config_response import AgentConfigResponse
from app.service.agent_config.content_response import AgentContentResponse
from app.service.agent_config.create_skill_request import CreateAgentSkillRequest
from app.service.agent_config.update_request import UpdateAgentContentRequest

router = APIRouter()


class AgentConfigRouter:
    @staticmethod
    def list_content(request: Request) -> AgentConfigResponse:
        repository = request.app.state.agent_content
        return AgentConfigResponse(
            prompts=repository.list_prompts(),
            skills=repository.list_skills(),
        )

    @staticmethod
    def update_content(
        kind: str, content_id: str,
        body: UpdateAgentContentRequest, request: Request,
    ) -> AgentContentResponse:
        try:
            return AgentContentResponse(
                **request.app.state.agent_content.update(
                    kind, content_id, body.content
                )
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @staticmethod
    def create_skill(
        body: CreateAgentSkillRequest, request: Request,
    ) -> AgentContentResponse:
        try:
            item = request.app.state.agent_content.add_skill(
                body.title, body.content
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        return AgentContentResponse(**item)


router.add_api_route(
    "/api/agent-config", AgentConfigRouter.list_content,
    methods=["GET"], response_model=AgentConfigResponse,
)
router.add_api_route(
    "/api/agent-config/{kind}/{content_id}",
    AgentConfigRouter.update_content,
    methods=["PUT"], response_model=AgentContentResponse,
)
router.add_api_route(
    "/api/agent-config/skills", AgentConfigRouter.create_skill,
    methods=["POST"], response_model=AgentContentResponse, status_code=201,
)
