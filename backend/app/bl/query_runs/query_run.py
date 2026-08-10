from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.bl.query_orchestrator.query_outcome import QueryOutcome


@dataclass
class QueryRun:
    id: str
    query: str
    status: str
    created_at: datetime
    updated_at: datetime
    pipeline_trace: List[Dict[str, Any]] = field(default_factory=list)
    outcome: Optional[QueryOutcome] = None
    error_type: Optional[str] = None
    error: Optional[str] = None
