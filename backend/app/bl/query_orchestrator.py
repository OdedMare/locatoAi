"""The full /api/query flow: select → describe → plan → validate → execute.

Current stage: layer selection is LIVE (agent call 1). Plan building
(agent call 2) is next — until it lands, a successful selection returns
a clarify response naming the chosen layers so the flow is testable
end-to-end from the UI.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

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
    timing_ms: Optional[Dict[str, int]] = None
    # Agent trace — what the model chose, so the UI can show its "thinking".
    selected_layers: List[LayerMeta] = field(default_factory=list)


class QueryOrchestrator:
    def __init__(
        self,
        catalog: CatalogService,
        executor: PlanExecutor,
        layer_selector: Optional[LayerSelector] = None,
    ):
        self._catalog = catalog
        self._executor = executor
        self._selector = layer_selector

    def run_query(self, query: str, boundaries: Optional[BaseGeometry]) -> QueryOutcome:
        """Natural-language entry point."""
        if self._selector is None:
            return QueryOutcome(
                status="clarify",
                clarify=(
                    "The AI agent is not wired up yet. "
                    "Use POST /api/execute-plan to run a hand-written plan."
                ),
            )

        started = time.perf_counter()
        selection = self._selector.select(query)
        select_ms = int((time.perf_counter() - started) * 1000)
        timing = {"select": select_ms}

        if selection.clarify:
            return QueryOutcome(status="clarify", clarify=selection.clarify, timing_ms=timing)

        # NEXT STAGE: build_plan(query, schemas of selected layers) →
        # validate (retry once) → execute. Until then, report the selection.
        names = ", ".join(layer.name for layer in selection.layers)
        return QueryOutcome(
            status="clarify",
            clarify="Layers selected: " + names + ". Plan building is the next stage.",
            timing_ms=timing,
            selected_layers=selection.layers,
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
