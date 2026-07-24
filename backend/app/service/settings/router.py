"""GET/PUT /api/settings with write-only secret handling."""

import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from app.bl.catalog.layers_repository import LayersRepository
from app.common.runtime_settings.runtime_settings import RuntimeSettings
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.service.settings.catalog_status import CatalogStatus
from app.service.settings.response import SettingsResponse
from app.service.settings.update import SettingsUpdate

router = APIRouter()


class SettingsRouter:
    @classmethod
    def get_settings(cls, request: Request) -> SettingsResponse:
        store: RuntimeSettingsStore = request.app.state.settings_store
        return cls.to_response(store.get(), request.app.state.repository)

    @classmethod
    def update_settings(
        cls, body: SettingsUpdate, request: Request
    ) -> SettingsResponse:
        store: RuntimeSettingsStore = request.app.state.settings_store
        patch = cls._clean_patch(body.model_dump(exclude_unset=True))
        try:
            settings = store.update(patch)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        return cls.to_response(settings, request.app.state.repository)

    @classmethod
    def to_response(
        cls, settings: RuntimeSettings, repository: LayersRepository
    ) -> SettingsResponse:
        values = {}
        values.update(cls._llm_values(settings))
        values.update(cls._provider_values(settings))
        values.update(cls._database_values(settings))
        values["catalog"] = cls.catalog_status(repository)
        return SettingsResponse(**values)

    @classmethod
    def _llm_values(cls, settings: RuntimeSettings) -> dict:
        return {
            "llm_model": settings.llm_model,
            "llm_diet_mode": settings.llm_diet_mode,
            "llm_base_url": settings.llm_base_url,
            "openai_api_key_set": bool(settings.openai_api_key),
            "openai_api_key_hint": cls.mask_key(settings.openai_api_key),
        }

    @staticmethod
    def _provider_values(settings: RuntimeSettings) -> dict:
        return {
            "mqs_base_url": settings.mqs_base_url,
            "mqs_user_id": settings.mqs_user_id,
            "mqs_verify_tls": settings.mqs_verify_tls,
            "cubes_base_url": settings.cubes_base_url,
            "cubes_token_set": bool(settings.cubes_token),
            "flapi_username": settings.flapi_username,
            "cubes_verify_tls": settings.cubes_verify_tls,
            "tyche_base_url": settings.tyche_base_url,
            "tyche_username": settings.tyche_username,
            "tyche_token_set": bool(settings.tyche_token),
            "tyche_verify_tls": settings.tyche_verify_tls,
        }

    @classmethod
    def _database_values(cls, settings: RuntimeSettings) -> dict:
        return {
            "database_url": cls.mask_db_password(settings.database_url),
            "database_user": settings.database_user,
            "database_password_set": bool(settings.database_password),
            "database_host": settings.database_host,
            "database_port": settings.database_port,
            "database_name": settings.database_name,
            "layers_table": settings.layers_table,
            "feedback_table": settings.feedback_table,
        }

    @staticmethod
    def _clean_patch(patch: dict) -> dict:
        for secret in (
            "openai_api_key", "database_password", "cubes_token", "tyche_token",
        ):
            if patch.get(secret) == "":
                patch.pop(secret)
        if "llm_model" in patch and not (patch.get("llm_model") or "").strip():
            patch.pop("llm_model")
        return patch

    @staticmethod
    def mask_key(key: str) -> Optional[str]:
        if not key:
            return None
        return f"…{key[-4:]}" if len(key) > 8 else "…"

    @staticmethod
    def mask_db_password(url: str) -> str:
        return re.sub(r"(://[^:/@]+):[^@/]+@", r"\1:****@", url)

    @staticmethod
    def catalog_status(repository: LayersRepository) -> CatalogStatus:
        try:
            return CatalogStatus(ok=True, layer_count=len(repository.list_layers()))
        except Exception as exc:
            return CatalogStatus(ok=False, error=str(exc))


get_settings = SettingsRouter.get_settings
update_settings = SettingsRouter.update_settings
_to_response = SettingsRouter.to_response
_mask_key = SettingsRouter.mask_key
_mask_db_password = SettingsRouter.mask_db_password
_catalog_status = SettingsRouter.catalog_status
router.add_api_route("/api/settings", get_settings, methods=["GET"], response_model=SettingsResponse)
router.add_api_route("/api/settings", update_settings, methods=["PUT"], response_model=SettingsResponse)
