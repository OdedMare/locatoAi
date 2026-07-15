from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import geopandas as gpd


@dataclass
class ExecutionOutput:
    """Executor result; scalar aggregations do not retain feature rows."""

    features: Optional[gpd.GeoDataFrame]
    scalar_result: Optional[int] = None
    step_traces: List[Dict[str, Any]] = field(default_factory=list)
