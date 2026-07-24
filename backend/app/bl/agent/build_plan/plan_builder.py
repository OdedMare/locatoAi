"""Build and revise validated geographic query plans."""

import json
from datetime import datetime
from pathlib import Path
from typing import Callable, List

from app.bl.agent.build_plan.geo_skill_catalog import GeoSkillCatalog
from app.bl.agent.build_plan.layer_prompt_formatter import LayerPromptFormatter
from app.bl.agent.build_plan.plan_build_loop import PlanBuildLoop
from app.bl.agent.build_plan.plan_build_result import PlanBuildResult
from app.bl.agent.build_plan.preserves_constraints import preserves_constraints
from app.bl.catalog.catalog_service import CatalogService
from app.bl.plan.models.geo_query_plan import GeoQueryPlan
from app.bl.catalog.models.layer_meta import LayerMeta
from app.bl.agent.llm_client import LLMClient

_PROMPTS = Path(__file__).parent.parent / "prompts"
_FALLBACK_CLARIFY = PlanBuildLoop._FALLBACK


class PlanBuilder:
    def __init__(
        self, llm: LLMClient, catalog: CatalogService,
        diet_mode: Callable[[], bool] = None,
        content_repository=None,
    ) -> None:
        self._content_repository = content_repository
        self._skills = GeoSkillCatalog(
            content_repository=content_repository, catalog=catalog
        )
        self._diet_mode = diet_mode or self._diet_disabled
        self._formatter = LayerPromptFormatter(catalog)
        self._loop = PlanBuildLoop(
            llm, catalog, skill_loader=self._skills.load_custom
        )

    def build(
        self, query: str, layers: List[LayerMeta],
        has_boundaries: bool, now: datetime,
    ) -> PlanBuildResult:
        diet = self._diet_mode()
        system = self._system_prompt(layers, has_boundaries, now, diet)
        selected_ids = {layer.id for layer in layers}
        return self._loop.run(
            query, system, selected_ids, has_boundaries, diet
        )

    def replan_after_empty(
        self, query: str, layers: List[LayerMeta], previous: GeoQueryPlan,
        has_boundaries: bool, now: datetime,
    ) -> PlanBuildResult:
        diagnostic = self._empty_diagnostic(query, previous)
        result = self.build(diagnostic, layers, has_boundaries, now)
        if result.plan is not None and not preserves_constraints(previous, result.plan):
            result.plan = None
            result.clarify = "לא נמצאו תוצאות, ותוכנית התיקון שינתה מגבלה מהבקשה."
        return result

    def _system_prompt(self, layers, has_boundaries, now, diet) -> str:
        name = "build_plan_diet.md" if diet else "build_plan.md"
        template = self._prompt(name)
        return (
            template.replace("{now}", now.isoformat())
            .replace("{has_boundaries}", "yes" if has_boundaries else "no")
            .replace(
                "{geo_skills}",
                self._skills.render(diet=diet, profile_ids=self._profile_ids(layers)),
            )
            .replace("{layers}", self._formatter.format(layers, diet))
        )

    def _prompt(self, name: str) -> str:
        if self._content_repository is not None:
            return self._content_repository.prompt(name)
        return (_PROMPTS / name).read_text(encoding="utf-8")

    @staticmethod
    def _empty_diagnostic(query: str, previous: GeoQueryPlan) -> str:
        return (
            query.strip()
            + "\n\nThe validated plan below executed successfully but returned zero rows. "
            + "Diagnose field/value or operation-order mistakes using tools and return "
            + "one revised plan. Preserve every user constraint exactly; never widen "
            + "time, distance, geography, counts, targets, or movement thresholds.\n"
            + json.dumps(previous.model_dump(by_alias=True), ensure_ascii=False)
        )

    @staticmethod
    def _diet_disabled() -> bool:
        return False

    @staticmethod
    def _profile_ids(layers) -> set:
        return {
            profile
            for layer in layers for profile in layer.profiles
        }
