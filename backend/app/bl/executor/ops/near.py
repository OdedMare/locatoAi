import geopandas as gpd
from shapely.geometry import mapping

from app.bl.executor.ops.base import ExecutionContext, OpHandler, register_op
from app.bl.plan.models.near_step import NearStep
from app.common.errors import ExecutionError
from app.common.geo import metric_crs_for, to_metric

# Computed distance to the nearest target-layer feature, in meters — added
# as a plain column so it survives every downstream op unchanged and is
# serialized into the GeoJSON response like any other property.
DISTANCE_COLUMN = "distance_to_target_m"
MATCH_REASON_COLUMN = "match_reason"
NEAREST_TARGET_COLUMN = "nearest_target_feature"


def _feature_from_row(row) -> dict:
    """Serialize the matched reference entity for the map/UI contract."""
    properties = {
        key: value.item() if hasattr(value, "item") else value
        for key, value in row.items()
        if key != "geometry"
    }
    return {
        "type": "Feature",
        "geometry": mapping(row.geometry),
        "properties": properties,
    }


def filter_reference_entities(target, field, operator, value):
    """Apply the optional named-landmark filter shared by proximity ops."""
    target_filter = (field, operator, value)
    if not any(item is not None for item in target_filter):
        return target
    if not all(item is not None for item in target_filter):
        raise ExecutionError(
            "proximity: target_field, target_operator and target_value "
            "must be supplied together"
        )
    if field not in target.columns:
        raise ExecutionError(f"proximity: target field '{field}' not in layer")
    column = target[field]
    if operator == "eq":
        return target[column == value]
    return target[
        column.astype(str).str.contains(
            str(value), case=False, na=False, regex=False
        )
    ]


def enrich_proximity_results(gdf, target, nearest_rows, requested_distance=None):
    """Attach distance, explanation and complete matched reference feature."""
    result = gdf.loc[nearest_rows.index].copy()
    distances = nearest_rows[DISTANCE_COLUMN]
    result[DISTANCE_COLUMN] = distances
    if requested_distance is None:
        result[MATCH_REASON_COLUMN] = [
            f"נבחר כאחת הישויות הקרובות ביותר; המרחק מישות הייחוס הוא "
            f"{round(float(distance))} מ׳."
            for distance in distances
        ]
    else:
        result[MATCH_REASON_COLUMN] = [
            f"נמצא במרחק {round(float(distance))} מ׳ מישות הייחוס "
            f"(בטווח המבוקש: {round(float(requested_distance))} מ׳)."
            for distance in distances
        ]
    result[NEAREST_TARGET_COLUMN] = [
        _feature_from_row(target.loc[target_index])
        for target_index in nearest_rows["index_right"]
    ]
    return result


@register_op("near")
class NearOp(OpHandler):
    """Keep input features within distance_m of ANY target-layer feature.

    Locked decision: meters math never happens in WGS84 degrees — both
    layers are reprojected to ITM (EPSG:2039) first.
    """

    def run(self, step: NearStep, ctx: ExecutionContext) -> gpd.GeoDataFrame:
        gdf = ctx.results[step.input]
        target = ctx.load_layer_features(step.target_layer)
        target = filter_reference_entities(
            target, step.target_field, step.target_operator, step.target_value
        )
        if gdf.empty or target.empty:
            result = gdf.iloc[0:0].copy()
            result[DISTANCE_COLUMN] = []
            result[MATCH_REASON_COLUMN] = []
            result[NEAREST_TARGET_COLUMN] = []
            return result

        metric_crs = metric_crs_for(gdf, target)
        left = to_metric(gdf, metric_crs)
        right = to_metric(target[["geometry"]], metric_crs)
        joined = gpd.sjoin_nearest(
            left, right, max_distance=step.distance_m, how="inner",
            distance_col=DISTANCE_COLUMN,
        )
        # Keep the actual nearest match, not only its distance: the client uses
        # it to render the reference pin, connecting arrow and entity popup.
        nearest_rows = joined.sort_values(DISTANCE_COLUMN).loc[
            lambda frame: ~frame.index.duplicated(keep="first")
        ]
        return enrich_proximity_results(
            gdf, target, nearest_rows, requested_distance=step.distance_m
        )
