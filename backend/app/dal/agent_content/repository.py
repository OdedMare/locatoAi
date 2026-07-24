"""File-backed defaults with runtime-persisted agent content overrides."""

from pathlib import Path
from typing import Dict, List
from uuid import uuid4

from app.bl.agent.skill_field_references import SkillFieldReferences
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore

_AGENT_ROOT = Path(__file__).parents[2] / "bl" / "agent"
_PROMPTS = _AGENT_ROOT / "prompts"
_SKILLS = _AGENT_ROOT / "skills" / "plan-geo-queries" / "references"
_PROFILES = _AGENT_ROOT / "skills" / "plan-geo-queries" / "profiles"
_REQUIRED_PROMPT_FIELDS = {
    "select_layers.md": ("{catalog}",),
    "select_layers_diet.md": ("{catalog}",),
    "build_plan.md": ("{now}", "{has_boundaries}", "{geo_skills}", "{layers}"),
    "build_plan_diet.md": (
        "{now}", "{has_boundaries}", "{geo_skills}", "{layers}",
    ),
}


class AgentContentRepository:
    def __init__(
        self, settings: RuntimeSettingsStore,
        prompts: Path = _PROMPTS, skills: Path = _SKILLS,
        profiles: Path = _PROFILES,
    ) -> None:
        self._settings = settings
        self._prompts = prompts
        self._skills = skills
        self._profiles = profiles

    def list_prompts(self) -> List[dict]:
        return [
            self._default_item("prompt", path)
            for path in sorted(self._prompts.glob("*.md"))
            if path.name != "README.md"
        ]

    def list_skills(self) -> List[dict]:
        return [
            *self.list_operation_skills(),
            *self.list_profiles(),
            *(
                self._custom_item(content_id, item)
                for content_id, item in self._custom_skills().items()
            ),
        ]

    def list_operation_skills(self) -> List[dict]:
        return [
            self._default_item("skill", path)
            for path in sorted(self._skills.glob("*.md"))
        ]

    def list_profiles(self) -> List[dict]:
        return [
            self._default_item("skill", path)
            for path in sorted(self._profiles.glob("*.md"))
        ]

    def prompt(self, content_id: str) -> str:
        return self._find(self.list_prompts(), content_id)["content"]

    def skill_contents(self) -> List[str]:
        return self.operation_skill_contents()

    def operation_skill_contents(self) -> List[str]:
        return [item["content"] for item in self.list_operation_skills()]

    def profile_contents(self, profile_ids) -> List[str]:
        requested = set(profile_ids)
        return [
            item["content"] for item in self.list_profiles()
            if Path(item["id"]).stem in requested
        ]

    def custom_skill_index(self) -> List[dict]:
        return [
            {
                "id": content_id,
                "title": str(item.get("title") or content_id),
                "description": self._use_when(str(item.get("content") or "")),
                "field_references": [
                    {"layer_id": layer_id, "field": field}
                    for layer_id, field in SkillFieldReferences.references(
                        str(item.get("content") or "")
                    )
                ],
            }
            for content_id, item in self._custom_skills().items()
        ]

    def custom_skill(self, content_id: str) -> str:
        item = self._custom_skills().get(content_id)
        return str(item.get("content") or "") if item else ""

    def update(self, kind: str, content_id: str, content: str) -> dict:
        content = self._clean_content(content)
        if kind not in ("prompt", "skill"):
            raise ValueError("Content kind must be prompt or skill")
        if kind == "prompt":
            self._validate_prompt(content_id, content)
        if kind == "skill" and content_id in self._custom_skills():
            return self._update_custom(content_id, content)
        items = self.list_prompts() if kind == "prompt" else self.list_skills()
        self._find(items, content_id)
        overrides = self._overrides()
        overrides[f"{kind}:{content_id}"] = content
        self._settings.update({"agent_content_overrides": overrides})
        return self._find(items, content_id, content)

    def add_skill(self, title: str, content: str) -> dict:
        title = title.strip()
        if not title:
            raise ValueError("Skill name is required")
        custom = self._custom_skills()
        if len(custom) >= 100:
            raise ValueError("Custom skill limit reached")
        content_id = f"custom-{uuid4().hex[:12]}"
        custom[content_id] = {
            "title": title[:120], "content": self._clean_content(content),
        }
        self._settings.update({"agent_custom_skills": custom})
        return self._custom_item(content_id, custom[content_id])

    def _default_item(self, kind: str, path: Path) -> dict:
        content_id = path.name
        source = path.read_text(encoding="utf-8")
        override = self._overrides().get(
            f"{kind}:{content_id}"
        )
        content = override if isinstance(override, str) else source
        return {
            "id": content_id,
            "title": self._title(content, path.stem),
            "kind": kind,
            "content": content,
            "is_custom": False,
            "is_overridden": isinstance(override, str),
        }

    @staticmethod
    def _custom_item(content_id: str, item: Dict[str, str]) -> dict:
        return {
            "id": content_id,
            "title": str(item.get("title") or content_id),
            "kind": "skill",
            "content": str(item.get("content") or ""),
            "is_custom": True,
            "is_overridden": False,
        }

    def _custom_skills(self) -> Dict[str, Dict[str, str]]:
        saved = self._settings.get().agent_custom_skills
        if not isinstance(saved, dict):
            return {}
        return {
            key: dict(value) for key, value in saved.items()
            if isinstance(key, str) and isinstance(value, dict)
        }

    def _overrides(self) -> Dict[str, str]:
        saved = self._settings.get().agent_content_overrides
        if not isinstance(saved, dict):
            return {}
        return {
            key: value for key, value in saved.items()
            if isinstance(key, str) and isinstance(value, str)
        }

    def _update_custom(self, content_id: str, content: str) -> dict:
        custom = self._custom_skills()
        custom[content_id]["content"] = content
        self._settings.update({"agent_custom_skills": custom})
        return self._custom_item(content_id, custom[content_id])

    @staticmethod
    def _find(items: List[dict], content_id: str, content: str = None) -> dict:
        for item in items:
            if item["id"] == content_id:
                changes = (
                    {"content": content, "is_overridden": True}
                    if content is not None else {}
                )
                return {**item, **changes}
        raise KeyError(f"Unknown agent content: {content_id}")

    @staticmethod
    def _clean_content(content: str) -> str:
        cleaned = content.strip()
        if not cleaned:
            raise ValueError("Agent content cannot be empty")
        if len(cleaned) > 100000:
            raise ValueError("Agent content is too long")
        return cleaned + "\n"

    @staticmethod
    def _validate_prompt(content_id: str, content: str) -> None:
        missing = [
            field for field in _REQUIRED_PROMPT_FIELDS.get(content_id, ())
            if field not in content
        ]
        if missing:
            raise ValueError(
                "Prompt must keep placeholders: " + ", ".join(missing)
            )

    @staticmethod
    def _title(content: str, fallback: str) -> str:
        first = content.strip().splitlines()[0] if content.strip() else ""
        if first.startswith("# "):
            return first[2:].replace("`", "").strip()
        return fallback.replace("_", " ").replace("-", " ")

    @staticmethod
    def _use_when(content: str) -> str:
        prefix = "**Use when:**"
        line = next(
            (line.strip() for line in content.splitlines()
             if line.strip().startswith(prefix)),
            "",
        )
        return line[len(prefix):].strip()[:240]
