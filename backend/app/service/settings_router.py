"""GET/PUT /api/settings — backs the UI settings panel.

Secrets are never echoed back: the API key is returned as a masked hint.
Sending an empty/omitted key on PUT keeps the existing one. Every GET/PUT
response includes live catalog status so the user immediately sees
whether their PG/table settings actually work.
"""

import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.bl.ports import LayersRepository
from app.common.runtime_settings import RuntimeSettings, RuntimeSettingsStore

router = APIRouter()


class SettingsUpdate(BaseModel):
    llm_model: Optional[str] = None
    llm_base_url: Optional[str] = None
    openai_api_key: Optional[str] = None  # empty/omitted = keep current
    mqs_base_url: Optional[str] = None
    mqs_user_id: Optional[str] = None
    cubes_base_url: Optional[str] = None
    cubes_token: Optional[str] = None  # empty/omitted = keep current
    database_url: Optional[str] = None
    database_user: Optional[str] = None
    database_password: Optional[str] = None  # empty/omitted = keep current
    database_host: Optional[str] = None
    database_port: Optional[int] = Field(default=None, ge=1, le=65535)
    database_name: Optional[str] = None
    layers_table: Optional[str] = None
    feedback_table: Optional[str] = None


class CatalogStatus(BaseModel):
    ok: bool
    layer_count: Optional[int] = None
    error: Optional[str] = None


class SettingsResponse(BaseModel):
    llm_model: str
    llm_base_url: Optional[str]
    openai_api_key_set: bool
    openai_api_key_hint: Optional[str]
    mqs_base_url: Optional[str]
    mqs_user_id: Optional[str]
    cubes_base_url: Optional[str]
    cubes_token_set: bool
    database_url: str
    database_user: str
    database_password_set: bool
    database_host: str
    database_port: Optional[int]
    database_name: str
    layers_table: str
    feedback_table: str
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
        mqs_base_url=settings.mqs_base_url,
        mqs_user_id=settings.mqs_user_id,
        cubes_base_url=settings.cubes_base_url,
        cubes_token_set=bool(settings.cubes_token),
        database_url=_mask_db_password(settings.database_url),
        database_user=settings.database_user,
        database_password_set=bool(settings.database_password),
        database_host=settings.database_host,
        database_port=settings.database_port,
        database_name=settings.database_name,
        layers_table=settings.layers_table,
        feedback_table=settings.feedback_table,
        catalog=_catalog_status(repository),
    )


@router.get("/api/settings", response_model=SettingsResponse)
def get_settings(request: Request) -> SettingsResponse:
    store: RuntimeSettingsStore = request.app.state.settings_store
    return _to_response(store.get(), request.app.state.repository)


@router.put("/api/settings", response_model=SettingsResponse)
def update_settings(body: SettingsUpdate, request: Request) -> SettingsResponse:
    store: RuntimeSettingsStore = request.app.state.settings_store
    patch = body.model_dump(exclude_unset=True)
    if patch.get("openai_api_key") == "":
        patch.pop("openai_api_key")  # empty = keep existing key
    if patch.get("database_password") == "":
        patch.pop("database_password")  # empty = keep existing password
    if patch.get("cubes_token") == "":
        patch.pop("cubes_token")  # empty = keep existing token
    if not (patch.get("llm_model") or "").strip() and "llm_model" in patch:
        patch.pop("llm_model")  # a model is always required — keep existing
    try:
        settings = store.update(patch)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _to_response(settings, request.app.state.repository)
