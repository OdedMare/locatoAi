"""GET/PUT /api/settings — backs the UI settings panel.

Secrets are never echoed back: the API key is returned as a masked hint.
Sending an empty/omitted key on PUT keeps the existing one. Every GET/PUT
response includes live catalog status so the user immediately sees
whether their PG/table settings actually work.
"""

import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from app.bl.ports.layers_repository import LayersRepository
from app.common.runtime_settings.runtime_settings import RuntimeSettings
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.service.settings_dto.catalog_status import CatalogStatus
from app.service.settings_dto.settings_response import SettingsResponse
from app.service.settings_dto.settings_update import SettingsUpdate

router = APIRouter()


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
        mqs_verify_tls=settings.mqs_verify_tls,
        cubes_base_url=settings.cubes_base_url,
        cubes_token_set=bool(settings.cubes_token),
        cubes_verify_tls=settings.cubes_verify_tls,
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
