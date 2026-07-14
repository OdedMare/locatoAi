import geopandas as gpd

from app.bl.executor.ops.base import ExecutionContext, OpHandler, register_op
from app.bl.plan.models import ClusterStep
from app.common.geo import metric_crs_for, to_metric

CLUSTER_ID_COLUMN = "cluster_id"


def _connected_components(pairs, node_count: int):
    """Union-find over 0-based row positions connected by `pairs` (i, j
    edges where i < j). Returns {position: component_id}, components
    numbered by first-seen order for determinism."""
    parent = list(range(node_count))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_b] = root_a

    for i, j in pairs:
        union(i, j)

    roots = [find(i) for i in range(node_count)]
    ids = {}
    for root in roots:
        if root not in ids:
            ids[root] = len(ids)
    return [ids[root] for root in roots]


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
            result = gdf.iloc[0:0].copy()
            result[CLUSTER_ID_COLUMN] = []
            return result

        metric = to_metric(gdf, metric_crs_for(gdf)).reset_index(drop=True)
        # Self-join: every pair of rows within max_distance_m of each
        # other becomes an edge (sjoin_nearest only gives the single
        # nearest match per row, which would miss valid group members).
        # The pinned geopandas (0.13.2) sjoin has no "dwithin" predicate/
        # distance kwarg (added in a later release) — buffer + intersects
        # is the equivalent available here.
        buffered = metric.copy()
        buffered["geometry"] = buffered.geometry.buffer(step.max_distance_m)
        joined = gpd.sjoin(buffered, metric, how="inner", predicate="intersects")
        pairs = [
            (left, right)
            for left, right in zip(joined.index, joined["index_right"])
            if left < right
        ]

        component_ids = _connected_components(pairs, len(metric))
        component_sizes: dict = {}
        for component_id in component_ids:
            component_sizes[component_id] = component_sizes.get(component_id, 0) + 1
        qualifying = {
            component_id
            for component_id, size in component_sizes.items()
            if size >= step.min_group_size
        }

        keep_positions = [
            position
            for position, component_id in enumerate(component_ids)
            if component_id in qualifying
        ]
        result = gdf.iloc[keep_positions].copy()
        result[CLUSTER_ID_COLUMN] = [component_ids[p] for p in keep_positions]
        return result
