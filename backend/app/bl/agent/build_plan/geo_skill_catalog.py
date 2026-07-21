"""Load model-facing GeoQueryPlan operation skills."""

from pathlib import Path


_REFERENCES = (
    Path(__file__).parent.parent / "skills" / "plan-geo-queries" / "references"
)


class GeoSkillCatalog:
    def __init__(self, references: Path = _REFERENCES) -> None:
        self._references = references

    def render(self) -> str:
        files = sorted(self._references.glob("*.md"))
        if not files:
            raise RuntimeError("Geo operation skills are missing")
        return "\n\n".join(
            path.read_text(encoding="utf-8").strip() for path in files
        )
