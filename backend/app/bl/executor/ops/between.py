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
        first, second = self._targets(step, ctx)
        if gdf.empty or first.empty or second.empty:
            return self._empty(gdf)
        self._validate_pair_count(first, second)
        corridor, candidates = self._corridor(gdf, first, second, step.corridor_width_m)
        mask = candidates.geometry.intersects(corridor)
        result = gdf.loc[mask[mask].index].copy()
        result["match_reason"] = (
            "הישות נמצאת במסדרון שבין שתי ישויות הייחוס "
            f"(רוחב {round(float(step.corridor_width_m))} מ׳)."
        )
        return result

    @staticmethod
    def _targets(step: BetweenStep, ctx: ExecutionContext):
        geometry_hint = ctx.proximity_geometry(step.corridor_width_m)
        first = filter_reference_entities(
            ctx.load_layer_features(step.first_target_layer, geometry_hint=geometry_hint),
            step.first_target_field,
            step.first_target_operator,
            step.first_target_value,
        )
        second = filter_reference_entities(
            ctx.load_layer_features(step.second_target_layer, geometry_hint=geometry_hint),
            step.second_target_field,
            step.second_target_operator,
            step.second_target_value,
        )
        return first, second

    @staticmethod
    def _validate_pair_count(first, second) -> None:
        if len(first) * len(second) > _MAX_REFERENCE_PAIRS:
            raise ExecutionError(
                "between: too many reference pairs; filter each target to a "
                "specific entity"
            )

    @staticmethod
    def _corridor(gdf, first, second, width):
        metric_crs = metric_crs_for(gdf, first, second)
        candidates = to_metric(gdf, metric_crs)
        first_metric = to_metric(first, metric_crs)
        second_metric = to_metric(second, metric_crs)
        corridors = [BetweenOp._corridor_between(left, right, width)
                     for left, right in product(first_metric.geometry,
                                                second_metric.geometry)]
        return unary_union(corridors), candidates

    @staticmethod
    def _corridor_between(first, second, width):
        start = first.representative_point()
        end = second.representative_point()
        return LineString([start, end]).buffer(width)

    @staticmethod
    def _empty(gdf):
        result = gdf.iloc[0:0].copy()
        result["match_reason"] = []
        return result
