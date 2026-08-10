from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.bl.query_runs.query_run import QueryRun
from app.service.query.response import QueryResponse


class QueryRunResponse(BaseModel):
    id: str
    status: Literal["queued", "running", "completed", "failed"]
    created_at: datetime
    updated_at: datetime
    pipeline_trace: List[Dict[str, Any]] = Field(default_factory=list)
    response: Optional[QueryResponse] = None
    error_type: Optional[str] = None
    error: Optional[str] = None

    @classmethod
    def from_run(cls, run: QueryRun) -> "QueryRunResponse":
        response = QueryResponse.from_outcome(run.outcome) if run.outcome else None
        if response is not None:
            response.request_id = run.id
        return cls(
            id=run.id, status=run.status,
            created_at=run.created_at, updated_at=run.updated_at,
            pipeline_trace=run.pipeline_trace, response=response,
            error_type=run.error_type, error=run.error,
        )
