"""Load model-facing GeoQueryPlan operation skills."""

from pathlib import Path

from app.bl.agent.build_plan.operation_contract_catalog import (
    OperationContractCatalog,
)

_REFERENCES = (
    Path(__file__).parent.parent / "skills" / "plan-geo-queries" / "references"
)
_PROFILES = (
    Path(__file__).parent.parent / "skills" / "plan-geo-queries" / "profiles"
)


class GeoSkillCatalog:
    def __init__(
        self, references: Path = _REFERENCES, profiles: Path = _PROFILES,
        content_repository=None,
    ) -> None:
        self._references = references
        self._profiles = profiles
        self._content_repository = content_repository
        self._contracts = OperationContractCatalog()

    def render(self, diet: bool = False, profile_ids=()) -> str:
        contents = self._operation_contents()
        if not contents:
            raise RuntimeError("Geo operation skills are missing")
        sections = [
            "CODE-DERIVED OPERATION CONTRACTS\n" + self._contracts.render(),
            "\n\n".join(self._render_content(item, diet) for item in contents),
        ]
        profiles = self._profile_contents(profile_ids)
        if profiles:
            sections.append("ACTIVE DOMAIN PROFILES\n" + "\n\n".join(profiles))
        custom_index = self._custom_index(diet)
        if custom_index:
            sections.append(custom_index)
        return "\n\n".join(sections)

    def load_custom(self, skill_id: str, diet: bool = False) -> str:
        if self._content_repository is None:
            return ""
        content = self._content_repository.custom_skill(skill_id).strip()
        return content[:1500 if diet else 4000]

    @staticmethod
    def _render_content(content: str, diet: bool) -> str:
        content = content.strip()
        if not diet:
            return content
        prefixes = ("# ", "**Use when:**", "**Do not use when:**")
        compact = "\n\n".join(
            line for line in content.splitlines() if line.startswith(prefixes)
        )
        return compact or content

    def _operation_contents(self):
        if self._content_repository is not None:
            return self._content_repository.operation_skill_contents()
        return [
            path.read_text(encoding="utf-8")
            for path in sorted(self._references.glob("*.md"))
        ]

    def _profile_contents(self, profile_ids):
        if self._content_repository is not None:
            return self._content_repository.profile_contents(profile_ids)
        requested = set(profile_ids)
        return [
            path.read_text(encoding="utf-8").strip()
            for path in sorted(self._profiles.glob("*.md"))
            if path.stem in requested
        ]

    def _custom_index(self, diet: bool) -> str:
        if self._content_repository is None:
            return ""
        items = self._content_repository.custom_skill_index()
        if not items:
            return ""
        limit = 120 if diet else 240
        lines = [
            "- {id} | {title} | {description}".format(
                id=item["id"],
                title=" ".join(item["title"].split())[:120],
                description=item["description"][:limit] or "(no use rule)",
            )
            for item in items
        ]
        return (
            "OPTIONAL CUSTOM SKILLS (index only)\n"
            "When one is relevant, request its body with "
            '{"tool":"load_skill","skill_id":"<id>"} before planning.\n'
            + "\n".join(lines)
        )
