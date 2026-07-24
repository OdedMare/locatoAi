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
        system = template.replace("{catalog}", self._formatter.format(layers, diet))
        data = self._llm.complete_json(system=system, user=query.strip())
        return self._mapper.from_response(data, layers)

    def _prompt(self, name: str) -> str:
        if self._content_repository is not None:
            return self._content_repository.prompt(name)
        return (_PROMPTS / name).read_text(encoding="utf-8")

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
