from app.bl.executor.ops.base.op_registry import register_op
from app.bl.executor.ops.spatial_relation.spatial_relation_op import SpatialRelationOp


@register_op("crosses")
class CrossesOp(SpatialRelationOp):
    predicate = "crosses"
    reason = "הישות חוצה ישות בשכבת הייחוס."
