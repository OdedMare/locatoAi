"""The full /api/query flow: select → build plan → validate → execute.

Both agent calls are LIVE. Clarify can come from either call (always
Hebrew); validation failures inside plan building retry once with the
error appended before falling back to clarify.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

from app.bl.agent.build_plan import PlanBuilder
from app.bl.agent.select_layers import LayerSelector
from app.bl.catalog.catalog_service import CatalogService
from app.bl.executor.engine import PlanExecutor
from app.bl.plan.models import GeoQueryPlan
from app.bl.plan.validators import validate_plan
from app.bl.ports import LayerMeta


@dataclass
class QueryOutcome:
    status: str  # "ok" | "clarify" | "error"
    clarify: Optional[str] = None
    plan: Optional[GeoQueryPlan] = None
    features: Optional[gpd.GeoDataFrame] = None
    scalar_result: Optional[int] = None
    """For count plans, set alongside the geometries that were counted."""
    timing_ms: Optional[Dict[str, int]] = None
    token_usage: Optional[Dict[str, int]] = None
    # Agent trace — what the model chose and why (the UI's "thinking" view).
    selected_layers: List[LayerMeta] = field(default_factory=list)
    reasoning: str = ""
    tool_calls: List[Dict[str, str]] = field(default_factory=list)
    """sample_field rounds the plan builder ran ({layer_id, field} each)."""


def _sum_usage(*usages) -> Optional[Dict[str, int]]:
    total: Optional[Dict[str, int]] = None
    for usage in usages:
        if not isinstance(usage, dict):
            continue
        if total is None:
            total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        for key in total:
            total[key] += int(usage.get(key, 0))
    return total


class _StageTimer:
    """Collects per-stage elapsed milliseconds."""

    def __init__(self) -> None:
        self.timing: Dict[str, int] = {}
        self._started = time.perf_counter()

    def mark(self, stage: str) -> None:
        now = time.perf_counter()
        self.timing[stage] = int((now - self._started) * 1000)
        self._started = now


class QueryOrchestrator:
    def __init__(
        self,
        catalog: CatalogService,
        executor: PlanExecutor,
        layer_selector: Optional[LayerSelector] = None,
        plan_builder: Optional[PlanBuilder] = None,
    ):
        self._catalog = catalog
        self._executor = executor
        self._selector = layer_selector
        self._builder = plan_builder

    def run_query(self, query: str, boundaries: Optional[BaseGeometry]) -> QueryOutcome:
        """Natural-language entry point: the full agent pipeline."""
        if self._selector is None or self._builder is None:
            return QueryOutcome(
                status="clarify",
                clarify="הסוכן אינו מחובר — השתמש ב-POST /api/execute-plan.",
            )

        now = datetime.now(timezone.utc)
        timer = _StageTimer()

        # 1. Layer selection (agent call 1)
        selection = self._selector.select(query)
        timer.mark("select")
        if selection.clarify:
            return QueryOutcome(
                status="clarify",
                clarify=selection.clarify,
                timing_ms=timer.timing,
                token_usage=selection.token_usage,
                reasoning=selection.reasoning,
            )

        # 2. Plan building (agent call 2) — validate → retry once → clarify
        build = self._builder.build(
            query, selection.layers, has_boundaries=boundaries is not None, now=now
        )
        timer.mark("plan")
        usage = _sum_usage(selection.token_usage, build.token_usage)
        if build.plan is None:
            return QueryOutcome(
                status="clarify",
                clarify=build.clarify,
                timing_ms=timer.timing,
                token_usage=usage,
                selected_layers=selection.layers,
                reasoning=selection.reasoning,
                tool_calls=build.tool_calls,
            )

        # 3. Execution
        result = self._executor.execute_detailed(
            build.plan, user_geometry=boundaries, now=now
        )
        timer.mark("execute")

        return QueryOutcome(
            status="ok",
            plan=build.plan,
            features=result.features,
            scalar_result=result.scalar_result,
            timing_ms=timer.timing,
            token_usage=usage,
            selected_layers=selection.layers,
            reasoning=selection.reasoning,
            tool_calls=build.tool_calls,
        )

    def execute_plan(
        self, plan: GeoQueryPlan, boundaries: Optional[BaseGeometry]
    ) -> QueryOutcome:
        """Validate and execute an explicit plan (debug path)."""
        known_ids = {layer.id for layer in self._catalog.list_layers()}
        validate_plan(plan, known_ids, has_user_geometry=boundaries is not None)

        timer = _StageTimer()
        result = self._executor.execute_detailed(plan, user_geometry=boundaries)
        timer.mark("execute")

        return QueryOutcome(
            status="ok",
            plan=plan,
            features=result.features,
            scalar_result=result.scalar_result,
            timing_ms=timer.timing,
        )
