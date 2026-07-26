import geopandas as gpd

from app.bl.executor.ops.base.execution_context import ExecutionContext
from app.bl.executor.ops.base.op_handler import OpHandler
from app.bl.executor.ops.near import filter_reference_entities


class SpatialRelationOp(OpHandler):
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
            return self._empty_like(gdf)

        # GeoPandas requires both sides in the same CRS for topological tests.
        if gdf.crs is None or target.crs is None:
            raise ValueError(f"{self.predicate}: input features have no CRS")
        right = target[["geometry"]].to_crs(gdf.crs)
        joined = gpd.sjoin(gdf, right, how="inner", predicate=self.predicate)
        indexes = joined.index[~joined.index.duplicated(keep="first")]
        result = gdf.loc[indexes].copy()
        result["match_reason"] = self.reason
        return result

    @staticmethod
    def _empty_like(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        result = gdf.iloc[0:0].copy()
        result["match_reason"] = []
        return result
