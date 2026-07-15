from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import geopandas as gpd


@dataclass
class ExecutionOutput:
    """Detailed result used by the API so every success keeps geometry."""

    features: gpd.GeoDataFrame
    scalar_result: Optional[int] = None
    step_traces: List[Dict[str, Any]] = None
