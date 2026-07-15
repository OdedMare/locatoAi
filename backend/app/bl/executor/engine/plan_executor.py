"""Plan execution engine.

Runs steps in list order — validators guarantee every `input` references
an earlier step, so list order IS a topological order. The engine knows
nothing about individual ops (OCP): it dispatches via the op registry.
"""

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

# Importing the package registers all op handlers (see ops/__init__.py).
import app.bl.executor.ops  # noqa: F401
from app.bl.catalog.catalog_service import CatalogService
from app.bl.executor.engine.execution_output import ExecutionOutput
from app.bl.executor.ops.base.execution_context import ExecutionContext
from app.bl.executor.ops.base.op_registry import get_op_handler
from app.bl.plan.models.count_step import CountStep
from app.bl.plan.models.geo_query_plan import GeoQueryPlan
from app.bl.ports.provider_registry import ProviderRegistry


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
        """Return matching geometries or a scalar count.

        The legacy ``execute`` method remains backward-compatible for internal
        callers. Terminal count queries release their feature rows before HTTP
        serialization, avoiding a large and redundant GeoJSON response.
        """
        ctx = ExecutionContext(
            catalog=self._catalog,
            providers=self._providers,
            user_geometry=user_geometry,
            now=now or datetime.now(timezone.utc),
        )
        step_traces: List[Dict[str, Any]] = []
        for step in plan.steps:
            handler = get_op_handler(step.op)
            input_ref = getattr(step, "input", None)
            input_count = (
                len(ctx.results[input_ref])
                if input_ref is not None and input_ref in ctx.results
                else None
            )
            started = time.perf_counter()
            result = handler.run(step, ctx)
            duration_ms = int((time.perf_counter() - started) * 1000)
            output_count = result if isinstance(result, int) else len(result)
            step_traces.append({
                "stage": "execute_step",
                "step_id": step.id,
                "operation": step.op,
                "input_count": input_count,
                "output_count": output_count,
                "duration_ms": duration_ms,
                "parameters": step.model_dump(
                    by_alias=True, exclude={"id", "op", "input"}
                ),
                "status": "completed",
            })
            if isinstance(step, CountStep):
                return ExecutionOutput(
                    features=None, scalar_result=result,
                    step_traces=step_traces,
                )
            ctx.results[step.id] = result
        return ExecutionOutput(
            features=ctx.results[plan.output], step_traces=step_traces
        )
