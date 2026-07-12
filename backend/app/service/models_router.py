"""Models available from an OpenAI-compatible LLM provider.

GET  /api/models — using the SAVED settings.
POST /api/models — using overrides from the settings form, so users can
test a base URL / API key BEFORE saving them.
"""

from typing import List, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.bl.ports import LLMClient

router = APIRouter()


class ModelsResponse(BaseModel):
    models: List[str]


class ModelsProbeRequest(BaseModel):
    llm_base_url: Optional[str] = None
    openai_api_key: Optional[str] = None  # empty/omitted = use the saved key


@router.get("/api/models", response_model=ModelsResponse)
def list_models(request: Request) -> ModelsResponse:
    client: LLMClient = request.app.state.llm_client
    return ModelsResponse(models=client.list_models())


@router.post("/api/models", response_model=ModelsResponse)
def probe_models(body: ModelsProbeRequest, request: Request) -> ModelsResponse:
    client: LLMClient = request.app.state.llm_client
    return ModelsResponse(
        models=client.list_models(
            base_url_override=(body.llm_base_url or "").strip() or None,
            api_key_override=(body.openai_api_key or "").strip() or None,
        )
    )
