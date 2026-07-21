import geopandas as gpd

from app.bl.executor.ops.base.execution_context import ExecutionContext
from app.bl.executor.ops.base.op_handler import OpHandler
from app.bl.executor.ops.base.op_registry import register_op
from app.bl.executor.ops.proximity_result_builder import ProximityResultBuilder
from app.bl.executor.ops.reference_entity_filter import ReferenceEntityFilter
from app.bl.plan.models.near_step import NearStep
from app.common.errors.execution_error import ExecutionError
from app.common.utils.geo_utils import metric_crs_for, to_metric

# Computed distance to the nearest target-layer feature, in meters — added
# as a plain column so it survives every downstream op unchanged and is
# serialized into the GeoJSON response like any other property.
_result_builder = ProximityResultBuilder()
DISTANCE_COLUMN = ProximityResultBuilder.DISTANCE_COLUMN
MATCH_REASON_COLUMN = ProximityResultBuilder.MATCH_REASON_COLUMN
NEAREST_TARGET_COLUMN = ProximityResultBuilder.NEAREST_TARGET_COLUMN
filter_reference_entities = ReferenceEntityFilter.apply
enrich_proximity_results = _result_builder.build
_feature_from_row = _result_builder._feature


@register_op("near")
class NearOp(OpHandler):
    """Keep input features within distance_m of ANY target-layer feature.

    Locked decision: meters math never happens in WGS84 degrees — both
    layers are reprojected to ITM (EPSG:2039) first.
    """

    def run(self, step: NearStep, ctx: ExecutionContext) -> gpd.GeoDataFrame:
        gdf = ctx.results[step.input]
        target = self._target(step, ctx)
        if gdf.empty or target.empty:
            return self._empty(gdf)
        joined = self._nearest_join(gdf, target, step.distance_m)
        nearest_rows = joined.sort_values(DISTANCE_COLUMN).loc[
            lambda frame: ~frame.index.duplicated(keep="first")
        ]
        return enrich_proximity_results(
            gdf, target, nearest_rows, requested_distance=step.distance_m
        )

    @staticmethod
    def _target(step: NearStep, ctx: ExecutionContext):
        target = ctx.load_layer_features(
            step.target_layer,
            geometry_hint=ctx.proximity_geometry(step.distance_m),
        )
        target = filter_reference_entities(
            target, step.target_field, step.target_operator, step.target_value
        )
        return target

    @staticmethod
    def _nearest_join(gdf, target, distance_m):
        metric_crs = metric_crs_for(gdf, target)
        left = to_metric(gdf, metric_crs)
        right = to_metric(target[["geometry"]], metric_crs)
        return gpd.sjoin_nearest(
            left, right, max_distance=distance_m, how="inner",
            distance_col=DISTANCE_COLUMN,
        )

    @staticmethod
    def _empty(gdf):
        result = gdf.iloc[0:0].copy()
        result[DISTANCE_COLUMN] = []
        result[MATCH_REASON_COLUMN] = []
        result[NEAREST_TARGET_COLUMN] = []
        return result
