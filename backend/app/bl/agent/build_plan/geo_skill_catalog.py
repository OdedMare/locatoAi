"""Load model-facing GeoQueryPlan operation skills."""

from pathlib import Path


_REFERENCES = (
    Path(__file__).parent.parent / "skills" / "plan-geo-queries" / "references"
)


class GeoSkillCatalog:
    def __init__(self, references: Path = _REFERENCES) -> None:
        self._references = references

    def render(self, diet: bool = False) -> str:
        files = sorted(self._references.glob("*.md"))
        if not files:
            raise RuntimeError("Geo operation skills are missing")
        return "\n\n".join(
            self._render_file(path, diet) for path in files
        )

    @staticmethod
    def _render_file(path: Path, diet: bool) -> str:
        content = path.read_text(encoding="utf-8").strip()
        if not diet:
            return content
        prefixes = ("# ", "**Use when:**", "**Do not use when:**", "**Emit:**")
        return "\n\n".join(
            line for line in content.splitlines() if line.startswith(prefixes)
        )
