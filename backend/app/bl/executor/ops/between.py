"""Select features in a configurable corridor between two references."""

from itertools import product

import geopandas as gpd
from shapely.geometry import LineString
from shapely.ops import unary_union

from app.bl.executor.ops.base.execution_context import ExecutionContext
from app.bl.executor.ops.base.op_handler import OpHandler
from app.bl.executor.ops.base.op_registry import register_op
from app.bl.executor.ops.near import filter_reference_entities
from app.bl.plan.models.between_step import BetweenStep
from app.common.errors.execution_error import ExecutionError
from app.common.geo import metric_crs_for, to_metric

_MAX_REFERENCE_PAIRS = 2500


@register_op("between")
class BetweenOp(OpHandler):
    """Keep input geometries intersecting corridors between reference pairs."""

    def run(self, step: BetweenStep, ctx: ExecutionContext) -> gpd.GeoDataFrame:
        gdf = ctx.results[step.input]
        first = filter_reference_entities(
            ctx.load_layer_features(step.first_target_layer),
            step.first_target_field,
            step.first_target_operator,
            step.first_target_value,
        )
        second = filter_reference_entities(
            ctx.load_layer_features(step.second_target_layer),
            step.second_target_field,
            step.second_target_operator,
            step.second_target_value,
        )
        if gdf.empty or first.empty or second.empty:
            result = gdf.iloc[0:0].copy()
            result["match_reason"] = []
            return result
        if len(first) * len(second) > _MAX_REFERENCE_PAIRS:
            raise ExecutionError(
                "between: too many reference pairs; filter each target to a "
                "specific entity"
            )

        metric_crs = metric_crs_for(gdf, first, second)
        candidates = to_metric(gdf, metric_crs)
        first_metric = to_metric(first, metric_crs)
        second_metric = to_metric(second, metric_crs)
        corridors = []
        for first_geometry, second_geometry in product(
            first_metric.geometry, second_metric.geometry
        ):
            start = first_geometry.representative_point()
            end = second_geometry.representative_point()
            corridors.append(
                LineString([start, end]).buffer(step.corridor_width_m)
            )
        corridor = unary_union(corridors)
        mask = candidates.geometry.intersects(corridor)
        result = gdf.loc[mask[mask].index].copy()
        result["match_reason"] = (
            "הישות נמצאת במסדרון שבין שתי ישויות הייחוס "
            f"(רוחב {round(float(step.corridor_width_m))} מ׳)."
        )
        return result
