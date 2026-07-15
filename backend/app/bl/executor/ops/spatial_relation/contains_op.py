from app.bl.executor.ops.base.op_registry import register_op
from app.bl.executor.ops.spatial_relation.spatial_relation_op import SpatialRelationOp


@register_op("contains")
class ContainsOp(SpatialRelationOp):
    predicate = "contains"
    reason = "הישות מכילה במלואה ישות משכבת הייחוס."
