"""GET/PUT /api/settings — backs the UI settings panel.

Secrets are never echoed back: the API key is returned as a masked hint.
Sending an empty/omitted key on PUT keeps the existing one. Every GET/PUT
response includes live catalog status so the user immediately sees
whether their PG/table settings actually work.
"""

import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.bl.ports import LayersRepository
from app.common.runtime_settings import RuntimeSettings, RuntimeSettingsStore

router = APIRouter()


class SettingsUpdate(BaseModel):
    llm_model: Optional[str] = None
    llm_base_url: Optional[str] = None
    openai_api_key: Optional[str] = None  # empty/omitted = keep current
    database_url: Optional[str] = None
    layers_table: Optional[str] = None


class CatalogStatus(BaseModel):
    ok: bool
    layer_count: Optional[int] = None
    error: Optional[str] = None


class SettingsResponse(BaseModel):
    llm_model: str
    llm_base_url: Optional[str]
    openai_api_key_set: bool
    openai_api_key_hint: Optional[str]
    database_url: str
    layers_table: str
    catalog: CatalogStatus


def _mask_key(key: str) -> Optional[str]:
    if not key:
        return None
    return f"…{key[-4:]}" if len(key) > 8 else "…"


def _mask_db_password(url: str) -> str:
    # postgresql://user:secret@host → postgresql://user:****@host
    return re.sub(r"(://[^:/@]+):[^@/]+@", r"\1:****@", url)


def _catalog_status(repository: LayersRepository) -> CatalogStatus:
    try:
        return CatalogStatus(ok=True, layer_count=len(repository.list_layers()))
    except Exception as exc:
        return CatalogStatus(ok=False, error=str(exc))


def _to_response(
    settings: RuntimeSettings, repository: LayersRepository
) -> SettingsResponse:
    return SettingsResponse(
        llm_model=settings.llm_model,
        llm_base_url=settings.llm_base_url,
        openai_api_key_set=bool(settings.openai_api_key),
        openai_api_key_hint=_mask_key(settings.openai_api_key),
        database_url=_mask_db_password(settings.database_url),
        layers_table=settings.layers_table,
        catalog=_catalog_status(repository),
    )


@router.get("/api/settings", response_model=SettingsResponse)
def get_settings(request: Request) -> SettingsResponse:
    store: RuntimeSettingsStore = request.app.state.settings_store
    return _to_response(store.get(), request.app.state.repository)


@router.put("/api/settings", response_model=SettingsResponse)
def update_settings(body: SettingsUpdate, request: Request) -> SettingsResponse:
    store: RuntimeSettingsStore = request.app.state.settings_store
    patch = body.model_dump(exclude_none=True)
    if patch.get("openai_api_key") == "":
        patch.pop("openai_api_key")  # empty = keep existing key
    try:
        settings = store.update(patch)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _to_response(settings, request.app.state.repository)
