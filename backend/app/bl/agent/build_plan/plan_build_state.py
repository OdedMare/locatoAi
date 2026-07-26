"""Mutable state for one bounded plan-building conversation."""

from typing import Dict, List

from app.bl.agent.build_plan.usage_accumulator import UsageAccumulator


class PlanBuildState:
    def __init__(self, query: str) -> None:
        self.query = query
        self.user = query.strip()
        self.usage = UsageAccumulator()
        self.tool_notes: List[str] = []
        self.tool_calls: List[Dict[str, str]] = []
        self.diagnostics: List[dict] = []
        self.attempt = 0
