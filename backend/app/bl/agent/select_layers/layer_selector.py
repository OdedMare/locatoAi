"""Select query-relevant layers from sanitized catalog metadata."""

from pathlib import Path
from typing import Callable

from app.bl.agent.select_layers.layer_catalog_formatter import LayerCatalogFormatter
from app.bl.agent.select_layers.layer_selection import LayerSelection
from app.bl.agent.select_layers.layer_selection_mapper import LayerSelectionMapper
from app.bl.catalog.catalog_service import CatalogService
from app.bl.agent.llm_client import LLMClient

_PROMPTS = Path(__file__).parent.parent / "prompts"
_FALLBACK_CLARIFY = LayerSelectionMapper.FALLBACK_CLARIFY


class LayerSelector:
    def __init__(
        self, llm: LLMClient, catalog: CatalogService,
        diet_mode: Callable[[], bool] = None,
        content_repository=None,
    ) -> None:
        self._llm = llm
        self._catalog = catalog
        self._content_repository = content_repository
        self._diet_mode = diet_mode or self._diet_disabled
        self._formatter = LayerCatalogFormatter()
        self._mapper = LayerSelectionMapper()

    def select(self, query: str) -> LayerSelection:
        layers = self._catalog.list_queryable_layers()
        if not layers:
            return self._no_layers()
        diet = self._diet_mode()
        name = "select_layers_diet.md" if diet else "select_layers.md"
        template = self._prompt(name)
        catalog = self._formatter.format(layers, diet)
        system = template.replace(
            "{catalog}", catalog + self._custom_skill_routes(layers, diet)
        )
        data = self._llm.complete_json(system=system, user=query.strip())
        return self._mapper.from_response(data, layers)

    def _prompt(self, name: str) -> str:
        if self._content_repository is not None:
            return self._content_repository.prompt(name)
        return (_PROMPTS / name).read_text(encoding="utf-8")

    def _custom_skill_routes(self, layers, diet: bool) -> str:
        if self._content_repository is None:
            return ""
        known = {layer.id for layer in layers}
        lines = []
        for item in self._content_repository.custom_skill_index():
            layer_ids = list(dict.fromkeys(
                reference["layer_id"]
                for reference in item.get("field_references", [])
                if reference["layer_id"] in known
            ))
            if not layer_ids:
                continue
            description = self._formatter.sanitize(
                item["description"], 100 if diet else 200
            )
            lines.append(
                "- {} | use={} | required_layer_ids={}".format(
                    self._formatter.sanitize(item["title"], 80),
                    description, ",".join(layer_ids),
                )
            )
        if not lines:
            return ""
        return (
            "\n\nCUSTOM SKILL ROUTES\n"
            "When the query matches a route, include all of its required layer ids.\n"
            + "\n".join(lines)
        )

    @staticmethod
    def _no_layers() -> LayerSelection:
        return LayerSelection(
            clarify="אין כרגע שכבות מידע פעילות — יש להפעיל ספק בקטלוג.",
            reasoning="כל שכבות הקטלוג משויכות לספקים שאינם פעילים.",
        )

    @staticmethod
    def _diet_disabled() -> bool:
        return False


_sanitize = LayerCatalogFormatter.sanitize
