from typing import Literal

from app.bl.plan.models.spatial_relation_step import SpatialRelationStep


class ContainsStep(SpatialRelationStep):
    op: Literal["contains"]
