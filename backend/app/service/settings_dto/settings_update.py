from typing import Optional

from pydantic import BaseModel, Field


class SettingsUpdate(BaseModel):
    llm_model: Optional[str] = None
    llm_base_url: Optional[str] = None
    openai_api_key: Optional[str] = None  # empty/omitted = keep current
    mqs_base_url: Optional[str] = None
    mqs_user_id: Optional[str] = None
    mqs_verify_tls: Optional[bool] = None
    cubes_base_url: Optional[str] = None
    cubes_token: Optional[str] = None  # empty/omitted = keep current
    cubes_verify_tls: Optional[bool] = None
    database_url: Optional[str] = None
    database_user: Optional[str] = None
    database_password: Optional[str] = None  # empty/omitted = keep current
    database_host: Optional[str] = None
    database_port: Optional[int] = Field(default=None, ge=1, le=65535)
    database_name: Optional[str] = None
    layers_table: Optional[str] = None
    feedback_table: Optional[str] = None
