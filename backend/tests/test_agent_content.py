from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.bl.agent.build_plan.geo_skill_catalog import GeoSkillCatalog
from app.common.config.settings import Settings
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.agent_content.repository import AgentContentRepository
from app.service.agent_config.router import router


def make_repository(tmp_path):
    prompts = tmp_path / "prompts"
    skills = tmp_path / "skills"
    prompts.mkdir(exist_ok=True)
    skills.mkdir(exist_ok=True)
    (prompts / "build_plan.md").write_text(
        "{now} {has_boundaries} {geo_skills} {layers}", encoding="utf-8"
    )
    (skills / "01-load.md").write_text(
        "# `load`\n\n**Emit:** `{\"op\":\"load\"}`", encoding="utf-8"
    )
    settings = Settings(
        _env_file=None,
        runtime_settings_file=str(tmp_path / "runtime-settings.json"),
    )
    store = RuntimeSettingsStore(settings)
    return AgentContentRepository(store, prompts=prompts, skills=skills)


def test_prompt_edits_persist_and_required_placeholders_are_protected(tmp_path):
    repository = make_repository(tmp_path)
    edited = "MARKER {now} {has_boundaries} {geo_skills} {layers}"

    repository.update("prompt", "build_plan.md", edited)

    reloaded = make_repository(tmp_path)
    assert reloaded.prompt("build_plan.md").startswith("MARKER")
    with pytest.raises(ValueError, match="placeholders"):
        repository.update("prompt", "build_plan.md", "missing fields")


def test_custom_skill_is_immediately_rendered_for_the_planner(tmp_path):
    repository = make_repository(tmp_path)

    created = repository.add_skill(
        "mission steps",
        "# `mission`\n\n**Use when:** mission\n\n**Emit:** existing operations",
    )

    rendered = GeoSkillCatalog(content_repository=repository).render()
    assert created["is_custom"] is True
    assert "# `mission`" in rendered


def test_agent_config_api_lists_edits_and_creates_content(tmp_path):
    app = FastAPI()
    app.state.agent_content = make_repository(tmp_path)
    app.include_router(router)
    client = TestClient(app)

    listed = client.get("/api/agent-config")
    assert listed.status_code == 200
    assert len(listed.json()["prompts"]) == 1

    created = client.post("/api/agent-config/skills", json={
        "title": "mission", "content": "# mission steps",
    })
    assert created.status_code == 201
    assert created.json()["is_custom"] is True

    updated = client.put(
        "/api/agent-config/skill/01-load.md",
        json={"content": "# `load`\n\n**Emit:** revised"},
    )
    assert updated.status_code == 200
    assert "revised" in updated.json()["content"]
