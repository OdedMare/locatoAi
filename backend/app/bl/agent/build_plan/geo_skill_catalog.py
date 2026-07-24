"""Load model-facing GeoQueryPlan operation skills."""

from pathlib import Path


_REFERENCES = (
    Path(__file__).parent.parent / "skills" / "plan-geo-queries" / "references"
)


class GeoSkillCatalog:
    def __init__(
        self, references: Path = _REFERENCES, content_repository=None
    ) -> None:
        self._references = references
        self._content_repository = content_repository

    def render(self, diet: bool = False) -> str:
        contents = self._contents()
        if not contents:
            raise RuntimeError("Geo operation skills are missing")
        return "\n\n".join(
            self._render_content(content, diet) for content in contents
        )

    @staticmethod
    def _render_content(content: str, diet: bool) -> str:
        content = content.strip()
        if not diet:
            return content
        prefixes = ("# ", "**Use when:**", "**Do not use when:**", "**Emit:**")
        compact = "\n\n".join(
            line for line in content.splitlines() if line.startswith(prefixes)
        )
        return compact or content

    def _contents(self):
        if self._content_repository is not None:
            return self._content_repository.skill_contents()
        return [
            path.read_text(encoding="utf-8")
            for path in sorted(self._references.glob("*.md"))
        ]
