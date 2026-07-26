"""Unsaved LLM connection settings used to probe models."""

from typing import Optional

from pydantic import BaseModel


class ModelsProbeRequest(BaseModel):
    llm_base_url: Optional[str] = None
    openai_api_key: Optional[str] = None  # empty/omitted = use the saved key
