from abc import ABC, abstractmethod
from typing import Union

import geopandas as gpd

from app.bl.executor.ops.base.execution_context import ExecutionContext
from app.bl.plan.models.step import Step


class OpHandler(ABC):
    """One handler per plan op."""

    @abstractmethod
    def run(self, step: Step, ctx: ExecutionContext) -> Union[gpd.GeoDataFrame, int]:
        """A GeoDataFrame for every op except a terminal `count` step,
        which returns a plain int (see engine.py and ops/count.py)."""
        ...
