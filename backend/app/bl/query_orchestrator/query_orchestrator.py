"""The full /api/query flow: select → build plan → validate → execute.

Both agent calls are LIVE. Clarify can come from either call (always
Hebrew); validation failures inside plan building retry once with the
error appended before falling back to clarify.
"""

from datetime import datetime, timezone
from typing import Optional

from shapely.geometry.base import BaseGeometry

from app.bl.agent.build_plan.plan_builder import PlanBuilder
from app.bl.agent.select_layers.layer_selector import LayerSelector
from app.bl.catalog.catalog_service import CatalogService
from app.bl.executor.engine.plan_executor import PlanExecutor
from app.bl.plan.models.geo_query_plan import GeoQueryPlan
from app.bl.plan.validators import validate_plan
from app.bl.query_orchestrator.query_outcome import QueryOutcome
from app.bl.query_orchestrator.stage_timer import StageTimer
from app.bl.query_orchestrator.sum_usage import sum_usage


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
        timer = StageTimer()

        # 1. Layer selection (agent call 1)
        selection = self._selector.select(query)
        timer.mark("select")
        selection_trace = {
            "stage": "layer_selection",
            "status": "completed" if selection.layers else "clarify",
            "duration_ms": timer.timing["select"],
            "selected_layer_ids": [layer.id for layer in selection.layers],
            "selected_layer_names": [layer.name for layer in selection.layers],
            "explanation": selection.reasoning,
        }
        if selection.clarify:
            return QueryOutcome(
                status="clarify",
                clarify=selection.clarify,
                timing_ms=timer.timing,
                token_usage=selection.token_usage,
                reasoning=selection.reasoning,
                pipeline_trace=[selection_trace],
            )

        # 2. Plan building (agent call 2) — validate → retry once → clarify
        build = self._builder.build(
            query, selection.layers, has_boundaries=boundaries is not None, now=now
        )
        timer.mark("plan")
        usage = sum_usage(selection.token_usage, build.token_usage)
        planning_trace = {
            "stage": "plan_building",
            "status": "completed" if build.plan is not None else "clarify",
            "duration_ms": timer.timing["plan"],
            "attempts": build.attempts,
            "tool_calls": build.tool_calls,
            "explanation": build.plan.explanation if build.plan else build.clarify,
        }
        if build.plan is None:
            return QueryOutcome(
                status="clarify",
                clarify=build.clarify,
                timing_ms=timer.timing,
                token_usage=usage,
                selected_layers=selection.layers,
                reasoning=selection.reasoning,
                tool_calls=build.tool_calls,
                pipeline_trace=[selection_trace, planning_trace],
            )

        # 3. Execution
        result = self._executor.execute_detailed(
            build.plan, user_geometry=boundaries, now=now
        )
        timer.mark("execute")
        plan = build.plan
        trace = [selection_trace, planning_trace, *result.step_traces]
        if len(result.features) == 0:
            revised = self._builder.replan_after_empty(
                query, selection.layers, plan, boundaries is not None, now
            )
            usage = sum_usage(usage, revised.token_usage)
            build.tool_calls.extend(revised.tool_calls)
            trace.append({
                "stage": "zero_result_diagnosis",
                "status": "completed" if revised.plan else "clarify",
                "attempts": revised.attempts,
                "tool_calls": revised.tool_calls,
                "explanation": revised.plan.explanation if revised.plan else revised.clarify,
            })
            if revised.plan is None:
                return QueryOutcome(
                    status="clarify",
                    clarify=revised.clarify or "לא נמצאו תוצאות. אפשר לחדד את הבקשה?",
                    plan=plan,
                    features=result.features,
                    scalar_result=result.scalar_result,
                    timing_ms=timer.timing,
                    token_usage=usage,
                    selected_layers=selection.layers,
                    reasoning=selection.reasoning,
                    tool_calls=build.tool_calls,
                    pipeline_trace=trace,
                )
            if revised.plan is not None:
                plan = revised.plan
                result = self._executor.execute_detailed(
                    plan, user_geometry=boundaries, now=now
                )
                timer.mark("re_execute")
                trace.extend(result.step_traces)

        return QueryOutcome(
            status="ok",
            plan=plan,
            features=result.features,
            scalar_result=result.scalar_result,
            timing_ms=timer.timing,
            token_usage=usage,
            selected_layers=selection.layers,
            reasoning=selection.reasoning,
            tool_calls=build.tool_calls,
            pipeline_trace=[
                *trace,
                {
                    "stage": "response",
                    "status": "completed",
                    "feature_count": len(result.features),
                    "scalar_result": result.scalar_result,
                    "geometry_returned": True,
                },
            ],
        )

    def execute_plan(
        self, plan: GeoQueryPlan, boundaries: Optional[BaseGeometry]
    ) -> QueryOutcome:
        """Validate and execute an explicit plan (debug path)."""
        known_ids = {layer.id for layer in self._catalog.list_layers()}
        validate_plan(plan, known_ids, has_user_geometry=boundaries is not None)

        timer = StageTimer()
        result = self._executor.execute_detailed(plan, user_geometry=boundaries)
        timer.mark("execute")

        return QueryOutcome(
            status="ok",
            plan=plan,
            features=result.features,
            scalar_result=result.scalar_result,
            timing_ms=timer.timing,
            pipeline_trace=[
                {
                    "stage": "plan_validation",
                    "status": "completed",
                    "explanation": plan.explanation,
                },
                *result.step_traces,
                {
                    "stage": "response",
                    "status": "completed",
                    "feature_count": len(result.features),
                    "scalar_result": result.scalar_result,
                    "geometry_returned": True,
                },
            ],
        )
