from typing import Literal

from app.bl.plan.models.spatial_relation_step import SpatialRelationStep


class TouchesStep(SpatialRelationStep):
    op: Literal["touches"]
