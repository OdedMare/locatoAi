from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class RuntimeSettings:
    llm_model: str
    llm_diet_mode: bool
    llm_base_url: Optional[str]
    openai_api_key: str
    mqs_base_url: Optional[str]
    mqs_user_id: Optional[str]
    mqs_verify_tls: bool
    cubes_base_url: Optional[str]
    cubes_token: str
    cubes_verify_tls: bool
    tyche_base_url: Optional[str]
    tyche_username: Optional[str]
    tyche_token: str
    tyche_verify_tls: bool
    database_url: str
    database_user: str
    database_password: str
    database_host: str
    database_port: Optional[int]
    database_name: str
    layers_table: str
    feedback_table: str
    agent_content_overrides: Dict[str, str] = field(default_factory=dict)
    agent_custom_skills: Dict[str, Dict[str, str]] = field(default_factory=dict)

    def quoted_layers_table(self) -> str:
        """The layers table as a safely quoted SQL identifier."""
        parts = self.layers_table.split(".")
        return ".".join(f'"{part}"' for part in parts)

    def quoted_feedback_table(self) -> str:
        """The feedback table as a safely quoted SQL identifier."""
        parts = self.feedback_table.split(".")
        return ".".join(f'"{part}"' for part in parts)
