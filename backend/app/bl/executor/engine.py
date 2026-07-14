"""Plan execution engine.

Runs steps in list order — validators guarantee every `input` references
an earlier step, so list order IS a topological order. The engine knows
nothing about individual ops (OCP): it dispatches via the op registry.
"""

from datetime import datetime, timezone
from typing import Optional, Union

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

# Importing the package registers all op handlers (see ops/__init__.py).
import app.bl.executor.ops  # noqa: F401
from app.bl.catalog.catalog_service import CatalogService
from app.bl.executor.ops.base import ExecutionContext, get_op_handler
from app.bl.plan.models import CountStep, GeoQueryPlan
from app.bl.ports import ProviderRegistry


class PlanExecutor:
    def __init__(self, catalog: CatalogService, providers: ProviderRegistry):
        self._catalog = catalog
        self._providers = providers

    def execute(
        self,
        plan: GeoQueryPlan,
        user_geometry: Optional[BaseGeometry] = None,
        now: Optional[datetime] = None,
    ) -> Union[gpd.GeoDataFrame, int]:
        """Run a validated plan and return the output step's result.

        A GeoDataFrame (WGS84) for every op except a terminal `count` step,
        which returns a plain int (validate_plan guarantees `count`, if
        present, is always exactly the plan's output — see validators.py).
        """
        ctx = ExecutionContext(
            catalog=self._catalog,
            providers=self._providers,
            user_geometry=user_geometry,
            now=now or datetime.now(timezone.utc),
        )
        for step in plan.steps:
            handler = get_op_handler(step.op)
            result = handler.run(step, ctx)
            if isinstance(step, CountStep):
                return result  # int — never stored in ctx.results
            ctx.results[step.id] = result
        return ctx.results[plan.output]
