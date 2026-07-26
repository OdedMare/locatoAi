from app.bl.executor.ops.base.op_registry import register_op
from app.bl.executor.ops.spatial_relation.spatial_relation_op import SpatialRelationOp


@register_op("touches")
class TouchesOp(SpatialRelationOp):
    predicate = "touches"
    reason = "גבול הישות נוגע בגבול ישות בשכבת הייחוס ללא חפיפה פנימית."
