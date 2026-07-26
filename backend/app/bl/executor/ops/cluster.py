import geopandas as gpd

from app.bl.executor.ops.base.execution_context import ExecutionContext
from app.bl.executor.ops.base.op_handler import OpHandler
from app.bl.executor.ops.base.op_registry import register_op
from app.bl.executor.ops.union_find import UnionFind
from app.bl.plan.models.cluster_step import ClusterStep
from app.common.utils.geo_utils import metric_crs_for, to_metric

CLUSTER_ID_COLUMN = "cluster_id"


@register_op("cluster")
class ClusterOp(OpHandler):
    """Keep features that belong to a group of >= min_group_size input
    rows all mutually within max_distance_m of each other.

    "Mutually within" is implemented as connected components of the
    within-distance graph (a distance-threshold self-join), not exact
    clique-finding (NP-hard, unnecessary here): every member of a
    component is within max_distance_m of at least one other component
    member, transitively — a close approximation of "N features near
    each other" that's cheap for realistic layer sizes.
    """

    def run(self, step: ClusterStep, ctx: ExecutionContext) -> gpd.GeoDataFrame:
        gdf = ctx.results[step.input]
        if len(gdf) < step.min_group_size:
            return self._empty(gdf)
        component_ids = self._component_ids(gdf, step.max_distance_m)
        qualifying = self._qualifying(component_ids, step.min_group_size)
        positions = [
            index for index, component_id in enumerate(component_ids)
            if component_id in qualifying
        ]
        result = gdf.iloc[positions].copy()
        result[CLUSTER_ID_COLUMN] = [component_ids[index] for index in positions]
        return result

    @staticmethod
    def _component_ids(gdf, max_distance_m):
        metric = to_metric(gdf, metric_crs_for(gdf)).reset_index(drop=True)
        buffered = metric.copy()
        buffered["geometry"] = buffered.geometry.buffer(max_distance_m)
        joined = gpd.sjoin(buffered, metric, how="inner", predicate="intersects")
        pairs = [
            (left, right)
            for left, right in zip(joined.index, joined["index_right"])
            if left < right
        ]
        return UnionFind(len(metric)).components(pairs)

    @staticmethod
    def _qualifying(component_ids, minimum_size: int) -> set:
        sizes: dict = {}
        for component_id in component_ids:
            sizes[component_id] = sizes.get(component_id, 0) + 1
        return {
            component_id for component_id, size in sizes.items()
            if size >= minimum_size
        }

    @staticmethod
    def _empty(gdf):
        result = gdf.iloc[0:0].copy()
        result[CLUSTER_ID_COLUMN] = []
        return result
