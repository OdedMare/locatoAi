from typing import Optional

from pydantic import BaseModel

from app.service.settings_dto.catalog_status import CatalogStatus


class SettingsResponse(BaseModel):
    llm_model: str
    llm_diet_mode: bool
    llm_base_url: Optional[str]
    openai_api_key_set: bool
    openai_api_key_hint: Optional[str]
    mqs_base_url: Optional[str]
    mqs_user_id: Optional[str]
    mqs_verify_tls: bool
    cubes_base_url: Optional[str]
    cubes_token_set: bool
    cubes_verify_tls: bool
    database_url: str
    database_user: str
    database_password_set: bool
    database_host: str
    database_port: Optional[int]
    database_name: str
    layers_table: str
    feedback_table: str
    catalog: CatalogStatus
