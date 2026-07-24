from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.bl.agent.build_plan.geo_skill_catalog import GeoSkillCatalog
from app.bl.agent.build_plan.plan_builder import PlanBuilder
from app.common.config.settings import Settings
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.agent_content.repository import AgentContentRepository
from app.service.agent_config.router import router


def make_repository(tmp_path):
    prompts = tmp_path / "prompts"
    skills = tmp_path / "skills"
    profiles = tmp_path / "profiles"
    prompts.mkdir(exist_ok=True)
    skills.mkdir(exist_ok=True)
    profiles.mkdir(exist_ok=True)
    (prompts / "build_plan.md").write_text(
        "{now} {has_boundaries} {geo_skills} {layers}", encoding="utf-8"
    )
    (skills / "01-load.md").write_text(
        "# `load`\n\n**Emit:** `{\"op\":\"load\"}`", encoding="utf-8"
    )
    (profiles / "our-force.md").write_text(
        "# OurForce mission profile\n\nPROFILE BODY", encoding="utf-8"
    )
    settings = Settings(
        _env_file=None,
        runtime_settings_file=str(tmp_path / "runtime-settings.json"),
    )
    store = RuntimeSettingsStore(settings)
    return AgentContentRepository(
        store, prompts=prompts, skills=skills, profiles=profiles
    )


def test_prompt_edits_persist_and_required_placeholders_are_protected(tmp_path):
    repository = make_repository(tmp_path)
    edited = "MARKER {now} {has_boundaries} {geo_skills} {layers}"

    repository.update("prompt", "build_plan.md", edited)

    reloaded = make_repository(tmp_path)
    assert reloaded.prompt("build_plan.md").startswith("MARKER")
    with pytest.raises(ValueError, match="placeholders"):
        repository.update("prompt", "build_plan.md", "missing fields")


def test_custom_skill_is_indexed_and_loaded_on_demand(tmp_path):
    repository = make_repository(tmp_path)

    created = repository.add_skill(
        "mission steps",
        "# `mission`\n\n**Use when:** mission\n\n**Emit:** existing operations",
    )

    rendered = GeoSkillCatalog(content_repository=repository).render()
    assert created["is_custom"] is True
    assert created["id"] in rendered
    assert "# `mission`" not in rendered
    assert GeoSkillCatalog(content_repository=repository).load_custom(
        created["id"]
    ).startswith("# `mission`")


def test_domain_profile_is_rendered_only_when_activated(tmp_path):
    skills = GeoSkillCatalog(content_repository=make_repository(tmp_path))

    assert "PROFILE BODY" not in skills.render()
    assert "PROFILE BODY" in skills.render(profile_ids={"our-force"})


def test_plan_loop_loads_custom_skill_before_planning(tmp_path, catalog):
    repository = make_repository(tmp_path)
    created = repository.add_skill(
        "mission steps",
        "# `mission`\n\n**Use when:** mission\n\n"
        "CUSTOM BODY @field[schools/city_en]",
    )
    plan = {
        "explanation": "מציג בתי ספר",
        "steps": [{"id": "s1", "op": "load", "layer": "schools"}],
        "output": "s1",
    }

    class SequenceLLM:
        def __init__(self):
            self.responses = [
                {"tool": "load_skill", "skill_id": created["id"]}, plan,
            ]
            self.calls = []

        def complete_json(self, system, user, schema=None):
            self.calls.append({"system": system, "user": user, "schema": schema})
            return self.responses.pop(0)

    llm = SequenceLLM()
    result = PlanBuilder(
        llm, catalog, content_repository=repository
    ).build(
        "mission", catalog.list_layers()[:1], False,
        datetime(2026, 7, 24, tzinfo=timezone.utc),
    )

    assert result.plan is not None
    assert result.tool_calls == [{"skill_id": created["id"]}]
    assert "CUSTOM BODY" not in llm.calls[0]["system"]
    assert "CUSTOM BODY @city_en (layer `בתי ספר`, id `schools`)" in (
        llm.calls[1]["user"]
    )


def test_agent_config_rejects_stale_skill_field_reference(tmp_path, catalog):
    app = FastAPI()
    app.state.agent_content = make_repository(tmp_path)
    app.state.catalog = catalog
    app.include_router(router)

    response = TestClient(app).post("/api/agent-config/skills", json={
        "title": "broken",
        "content": "# broken\n\n@field[schools/not-a-real-field]",
    })

    assert response.status_code == 422
    assert "unavailable" in response.json()["detail"]


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
