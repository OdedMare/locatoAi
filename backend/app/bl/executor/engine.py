"""Plan execution engine.

Runs steps in list order — validators guarantee every `input` references
an earlier step, so list order IS a topological order. The engine knows
nothing about individual ops (OCP): it dispatches via the op registry.
"""

from datetime import datetime, timezone

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

# Importing the package registers all op handlers (see ops/__init__.py).
import app.bl.executor.ops  # noqa: F401
from app.bl.catalog.catalog_service import CatalogService
from app.bl.executor.ops.base import ExecutionContext, get_op_handler
from app.bl.plan.models import GeoQueryPlan
from app.bl.ports import ProviderRegistry


class PlanExecutor:
    def __init__(self, catalog: CatalogService, providers: ProviderRegistry):
        self._catalog = catalog
        self._providers = providers

    def execute(
        self,
        plan: GeoQueryPlan,
        user_geometry: BaseGeometry | None = None,
        now: datetime | None = None,
    ) -> gpd.GeoDataFrame:
        """Run a validated plan and return the output step's features (WGS84)."""
        ctx = ExecutionContext(
            catalog=self._catalog,
            providers=self._providers,
            user_geometry=user_geometry,
            now=now or datetime.now(timezone.utc),
        )
        for step in plan.steps:
            handler = get_op_handler(step.op)
            ctx.results[step.id] = handler.run(step, ctx)
        return ctx.results[plan.output]
