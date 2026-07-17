"""Models available from an OpenAI-compatible LLM provider.

GET  /api/models — using the SAVED settings.
POST /api/models — using overrides from the settings form, so users can
test a base URL / API key BEFORE saving them.
"""

from fastapi import APIRouter, Request

from app.bl.ports.llm_client import LLMClient
from app.service.models_dto.models_probe_request import ModelsProbeRequest
from app.service.models_dto.models_response import ModelsResponse

router = APIRouter()


class ModelsRouter:
    @staticmethod
    def list_models(request: Request) -> ModelsResponse:
        client: LLMClient = request.app.state.llm_client
        return ModelsResponse(models=client.list_models())

    @staticmethod
    def probe_models(
        body: ModelsProbeRequest, request: Request
    ) -> ModelsResponse:
        client: LLMClient = request.app.state.llm_client
        return ModelsResponse(
            models=client.list_models(
                base_url_override=(body.llm_base_url or "").strip() or None,
                api_key_override=(body.openai_api_key or "").strip() or None,
            )
        )


list_models = ModelsRouter.list_models
probe_models = ModelsRouter.probe_models
router.add_api_route("/api/models", list_models, methods=["GET"], response_model=ModelsResponse)
router.add_api_route("/api/models", probe_models, methods=["POST"], response_model=ModelsResponse)
