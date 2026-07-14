"""Plan execution engine.

Runs steps in list order — validators guarantee every `input` references
an earlier step, so list order IS a topological order. The engine knows
nothing about individual ops (OCP): it dispatches via the op registry.
"""

from dataclasses import dataclass
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


@dataclass
class ExecutionOutput:
    """Detailed result used by the API so every success keeps geometry."""

    features: gpd.GeoDataFrame
    scalar_result: Optional[int] = None


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
        output = self.execute_detailed(plan, user_geometry=user_geometry, now=now)
        return (
            output.scalar_result
            if output.scalar_result is not None
            else output.features
        )

    def execute_detailed(
        self,
        plan: GeoQueryPlan,
        user_geometry: Optional[BaseGeometry] = None,
        now: Optional[datetime] = None,
    ) -> ExecutionOutput:
        """Return matching geometries as well as an optional scalar count.

        The legacy ``execute`` method remains backward-compatible for internal
        callers. HTTP orchestration uses this method so count queries do not
        throw away the entities that were counted.
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
                return ExecutionOutput(
                    features=ctx.results[step.input], scalar_result=result
                )
            ctx.results[step.id] = result
        return ExecutionOutput(features=ctx.results[plan.output])
