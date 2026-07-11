"""GET /api/models — models available from the configured LLM provider."""

from typing import List

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.bl.ports import LLMClient

router = APIRouter()


class ModelsResponse(BaseModel):
    models: List[str]


@router.get("/api/models", response_model=ModelsResponse)
def list_models(request: Request) -> ModelsResponse:
    client: LLMClient = request.app.state.llm_client
    return ModelsResponse(models=client.list_models())
