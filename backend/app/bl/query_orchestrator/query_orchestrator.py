"""The full /api/query flow: select → build plan → validate → execute.

Both agent calls are LIVE. Clarify can come from either call (always
Hebrew); validation failures inside plan building retry once with the
error appended before falling back to clarify.
"""

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from shapely.geometry.base import BaseGeometry

from app.bl.agent.build_plan.plan_builder import PlanBuilder
from app.bl.agent.build_plan.plan_build_result import PlanBuildResult
from app.bl.agent.select_layers.layer_selection import LayerSelection
from app.bl.agent.select_layers.layer_selector import LayerSelector
from app.bl.catalog.catalog_service import CatalogService
from app.bl.executor.engine.plan_executor import PlanExecutor
from app.bl.executor.engine.execution_output import ExecutionOutput
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

    def run_query(
        self, query: str, boundaries: Optional[BaseGeometry],
        event_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> QueryOutcome:
        if self._selector is None or self._builder is None:
            return self._disconnected_outcome()
        now = datetime.now(timezone.utc)
        timer = StageTimer()
        selection, selection_trace = self._select(query, timer, event_sink)
        if selection.clarify:
            return self._selection_clarify(selection, selection_trace, timer)
        build, planning_trace = self._build(
            query, boundaries, now, selection, timer, event_sink
        )
        usage = sum_usage(selection.token_usage, build.token_usage)
        if build.plan is None:
            return self._planning_clarify(
                selection, build, [selection_trace, planning_trace], timer, usage
            )
        return self._execute_query(
            query, boundaries, now, selection, build,
            [selection_trace, planning_trace], timer, usage, event_sink,
        )

    def _select(self, query: str, timer: StageTimer, event_sink
                ) -> Tuple[LayerSelection, dict]:
        selection = self._run_stage(
            "layer_selection", lambda: self._selector.select(query), event_sink
        )
        timer.mark("select")
        trace = {
            "stage": "layer_selection", "duration_ms": timer.timing["select"],
            "status": "completed" if selection.layers else "clarify",
            "selected_layer_ids": [layer.id for layer in selection.layers],
            "selected_layer_names": [layer.name for layer in selection.layers],
            "requested_layer_ids": selection.requested_layer_ids,
            "dropped_layer_ids": selection.dropped_layer_ids,
            "clarify": selection.clarify,
            "explanation": selection.reasoning,
        }
        self._emit(event_sink, trace)
        return selection, trace

    def _build(self, query: str, boundaries: Optional[BaseGeometry],
               now: datetime, selection: LayerSelection,
               timer: StageTimer, event_sink) -> Tuple[PlanBuildResult, dict]:
        build = self._run_stage(
            "plan_building",
            lambda: self._builder.build(
                query, selection.layers, boundaries is not None, now
            ),
            event_sink,
        )
        timer.mark("plan")
        trace = {
            "stage": "plan_building", "duration_ms": timer.timing["plan"],
            "status": "completed" if build.plan is not None else "clarify",
            "attempts": build.attempts, "tool_calls": build.tool_calls,
            "diagnostics": build.diagnostics,
            "explanation": build.plan.explanation if build.plan else build.clarify,
        }
        self._emit(event_sink, trace)
        return build, trace

    def _execute_query(self, query: str, boundaries: Optional[BaseGeometry],
                       now: datetime, selection: LayerSelection,
                       build: PlanBuildResult, trace: List[Dict[str, Any]],
                       timer: StageTimer, usage: Optional[Dict[str, int]],
                       event_sink) -> QueryOutcome:
        result = self._run_stage(
            "execution",
            lambda: self._executor.execute_detailed(
                build.plan, boundaries, now, trace_sink=event_sink
            ),
            event_sink,
        )
        timer.mark("execute")
        trace.extend(result.step_traces)
        if self._has_results(result):
            return self._success(selection, build, build.plan, result,
                                 trace, timer, usage, event_sink)
        return self._handle_empty(query, boundaries, now, selection, build,
                                  result, trace, timer, usage, event_sink)

    def _handle_empty(self, query: str, boundaries: Optional[BaseGeometry],
                      now: datetime, selection: LayerSelection,
                      build: PlanBuildResult, result: ExecutionOutput,
                      trace: List[Dict[str, Any]], timer: StageTimer,
                      usage: Optional[Dict[str, int]], event_sink) -> QueryOutcome:
        revised = self._run_stage(
            "zero_result_diagnosis",
            lambda: self._builder.replan_after_empty(
                query, selection.layers, build.plan, boundaries is not None, now
            ),
            event_sink,
        )
        build.tool_calls.extend(revised.tool_calls)
        usage = sum_usage(usage, revised.token_usage)
        revision_trace = self._revision_trace(revised)
        trace.append(revision_trace)
        self._emit(event_sink, revision_trace)
        if revised.plan is None:
            return self._empty_clarify(selection, build, result, trace, timer, usage,
                                       revised.clarify)
        result = self._run_stage(
            "re_execution",
            lambda: self._executor.execute_detailed(
                revised.plan, boundaries, now, trace_sink=event_sink
            ),
            event_sink,
        )
        timer.mark("re_execute")
        trace.extend(result.step_traces)
        return self._success(selection, build, revised.plan, result,
                             trace, timer, usage, event_sink)

    @staticmethod
    def _has_results(result: ExecutionOutput) -> bool:
        if result.scalar_result is not None:
            return result.scalar_result > 0
        return result.features is not None and len(result.features) > 0

    @staticmethod
    def _revision_trace(revised: PlanBuildResult) -> dict:
        return {
            "stage": "zero_result_diagnosis",
            "status": "completed" if revised.plan else "clarify",
            "attempts": revised.attempts, "tool_calls": revised.tool_calls,
            "diagnostics": revised.diagnostics,
            "explanation": revised.plan.explanation if revised.plan else revised.clarify,
        }

    @staticmethod
    def _emit(event_sink, event: Dict[str, Any]) -> None:
        if event_sink is not None:
            event_sink(event)

    @staticmethod
    def _run_stage(stage: str, action, event_sink):
        QueryOrchestrator._emit(event_sink, {"stage": stage, "status": "started"})
        try:
            return action()
        except Exception as exc:
            QueryOrchestrator._emit(event_sink, {
                "stage": stage, "status": "failed",
                "error_type": type(exc).__name__, "error": str(exc),
            })
            raise

    @staticmethod
    def _disconnected_outcome() -> QueryOutcome:
        return QueryOutcome(
            status="clarify",
            clarify="הסוכן אינו מחובר — השתמש ב-POST /api/execute-plan.",
        )

    @staticmethod
    def _selection_clarify(selection: LayerSelection, trace: dict,
                           timer: StageTimer) -> QueryOutcome:
        return QueryOutcome(
            status="clarify", clarify=selection.clarify,
            timing_ms=timer.timing, token_usage=selection.token_usage,
            reasoning=selection.reasoning, pipeline_trace=[trace],
        )

    @staticmethod
    def _planning_clarify(selection: LayerSelection, build: PlanBuildResult,
                          trace: List[dict], timer: StageTimer,
                          usage: Optional[Dict[str, int]]) -> QueryOutcome:
        return QueryOutcome(
            status="clarify", clarify=build.clarify, timing_ms=timer.timing,
            token_usage=usage, selected_layers=selection.layers,
            reasoning=selection.reasoning, tool_calls=build.tool_calls,
            pipeline_trace=trace,
        )

    @staticmethod
    def _empty_clarify(selection: LayerSelection, build: PlanBuildResult,
                       result: ExecutionOutput, trace: List[dict], timer: StageTimer,
                       usage: Optional[Dict[str, int]], clarify: Optional[str]) -> QueryOutcome:
        return QueryOutcome(
            status="clarify", clarify=clarify or "לא נמצאו תוצאות. אפשר לחדד את הבקשה?",
            plan=build.plan, features=result.features,
            scalar_result=result.scalar_result, timing_ms=timer.timing,
            token_usage=usage, selected_layers=selection.layers,
            reasoning=selection.reasoning, tool_calls=build.tool_calls,
            pipeline_trace=trace,
        )

    @staticmethod
    def _success(selection: LayerSelection, build: PlanBuildResult,
                 plan: GeoQueryPlan, result: ExecutionOutput,
                 trace: List[dict], timer: StageTimer,
                 usage: Optional[Dict[str, int]], event_sink=None) -> QueryOutcome:
        response_trace = QueryOrchestrator._response_trace(result)
        trace.append(response_trace)
        QueryOrchestrator._emit(event_sink, response_trace)
        return QueryOutcome(
            status="ok", plan=plan, features=result.features,
            scalar_result=result.scalar_result, timing_ms=timer.timing,
            token_usage=usage, selected_layers=selection.layers,
            reasoning=selection.reasoning, tool_calls=build.tool_calls,
            pipeline_trace=trace,
        )

    @staticmethod
    def _response_trace(result: ExecutionOutput) -> dict:
        return {
            "stage": "response", "status": "completed",
            "feature_count": len(result.features) if result.features is not None else 0,
            "scalar_result": result.scalar_result,
            "geometry_returned": result.features is not None,
        }

    def execute_plan(
        self, plan: GeoQueryPlan, boundaries: Optional[BaseGeometry]
    ) -> QueryOutcome:
        self._validate_explicit_plan(plan, boundaries)
        timer = StageTimer()
        result = self._executor.execute_detailed(plan, user_geometry=boundaries)
        timer.mark("execute")
        return QueryOutcome(
            status="ok",
            plan=plan,
            features=result.features,
            scalar_result=result.scalar_result,
            timing_ms=timer.timing,
            pipeline_trace=self._explicit_trace(plan, result),
        )

    def _validate_explicit_plan(self, plan: GeoQueryPlan,
                                boundaries: Optional[BaseGeometry]) -> None:
        known_ids = {layer.id for layer in self._catalog.list_queryable_layers()}
        validate_plan(plan, known_ids, has_user_geometry=boundaries is not None)

    @staticmethod
    def _explicit_trace(plan: GeoQueryPlan, result: ExecutionOutput) -> List[dict]:
        validation = {
            "stage": "plan_validation", "status": "completed",
            "explanation": plan.explanation,
        }
        return [validation, *result.step_traces,
                QueryOrchestrator._response_trace(result)]
