"""The full /api/query flow: select → describe → plan → validate → execute.

Day 1: the agent steps are stubbed — the orchestrator returns a clarify
response explaining the agent isn't wired yet. The validate → execute
path is fully real and exercised via /api/execute-plan.

Day 2 replaces `_run_agent` with the two agent calls and inherits the
retry-once-on-invalid-plan + clarify-fallback policy without touching
the service or DAL tiers.
"""

import time
from dataclasses import dataclass
from typing import Dict, Optional

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

from app.bl.catalog.catalog_service import CatalogService
from app.bl.executor.engine import PlanExecutor
from app.bl.plan.models import GeoQueryPlan
from app.bl.plan.validators import validate_plan


@dataclass
class QueryOutcome:
    status: str  # "ok" | "clarify" | "error"
    clarify: Optional[str] = None
    plan: Optional[GeoQueryPlan] = None
    features: Optional[gpd.GeoDataFrame] = None
    timing_ms: Optional[Dict[str, int]] = None


class QueryOrchestrator:
    def __init__(self, catalog: CatalogService, executor: PlanExecutor):
        self._catalog = catalog
        self._executor = executor

    def run_query(self, query: str, boundaries: Optional[BaseGeometry]) -> QueryOutcome:
        """Natural-language entry point. Agent-backed from Day 2."""
        # DAY 2: select_layers → get_schema per layer → build_plan →
        #        validate_plan (retry once on failure) → execute_plan.
        return QueryOutcome(
            status="clarify",
            clarify=(
                "The AI agent is not wired up yet (Day 2). "
                "Use POST /api/execute-plan to run a hand-written plan."
            ),
        )

    def execute_plan(
        self, plan: GeoQueryPlan, boundaries: Optional[BaseGeometry]
    ) -> QueryOutcome:
        """Validate and execute an explicit plan (debug path, real logic)."""
        known_ids = {layer.id for layer in self._catalog.list_layers()}
        validate_plan(plan, known_ids, has_user_geometry=boundaries is not None)

        started = time.perf_counter()
        features = self._executor.execute(plan, user_geometry=boundaries)
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        return QueryOutcome(
            status="ok",
            plan=plan,
            features=features,
            timing_ms={"execute": elapsed_ms},
        )
