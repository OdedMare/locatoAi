"""Topological relations between the current result and a reference layer."""

import geopandas as gpd

from app.bl.executor.ops.base import ExecutionContext, OpHandler, register_op
from app.bl.executor.ops.near import filter_reference_entities
from app.bl.plan.models import ContainsStep, CrossesStep, TouchesStep


def _empty_like(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    result = gdf.iloc[0:0].copy()
    result["match_reason"] = []
    return result


class _SpatialRelationOp(OpHandler):
    predicate = ""
    reason = ""

    def run(self, step, ctx: ExecutionContext) -> gpd.GeoDataFrame:
        gdf = ctx.results[step.input]
        target = filter_reference_entities(
            ctx.load_layer_features(step.target_layer),
            step.target_field,
            step.target_operator,
            step.target_value,
        )
        if gdf.empty or target.empty:
            return _empty_like(gdf)

        # GeoPandas requires both sides in the same CRS for topological tests.
        if gdf.crs is None or target.crs is None:
            raise ValueError(f"{self.predicate}: input features have no CRS")
        right = target[["geometry"]].to_crs(gdf.crs)
        joined = gpd.sjoin(gdf, right, how="inner", predicate=self.predicate)
        indexes = joined.index[~joined.index.duplicated(keep="first")]
        result = gdf.loc[indexes].copy()
        result["match_reason"] = self.reason
        return result


@register_op("crosses")
class CrossesOp(_SpatialRelationOp):
    predicate = "crosses"
    reason = "הישות חוצה ישות בשכבת הייחוס."


@register_op("touches")
class TouchesOp(_SpatialRelationOp):
    predicate = "touches"
    reason = "גבול הישות נוגע בגבול ישות בשכבת הייחוס ללא חפיפה פנימית."


@register_op("contains")
class ContainsOp(_SpatialRelationOp):
    predicate = "contains"
    reason = "הישות מכילה במלואה ישות משכבת הייחוס."
