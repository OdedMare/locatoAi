import geopandas as gpd
from shapely.geometry import Point, box

from app.common.geo import buffer_wgs84_geometry, metric_crs_for, to_metric


def test_metric_crs_is_estimated_for_data_location_not_fixed_to_israel():
    los_angeles = gpd.GeoDataFrame(
        {"geometry": [Point(-118.4912, 33.9850)]}, crs="EPSG:4326"
    )
    crs = metric_crs_for(los_angeles)

    assert crs.to_epsg() == 32611
    projected = to_metric(los_angeles, crs)
    assert projected.crs.to_epsg() == 32611


def test_buffer_wgs84_geometry_expands_in_meters():
    boundary = box(34.77, 32.07, 34.78, 32.08)
    expanded = buffer_wgs84_geometry(boundary, 300)

    assert expanded.covers(boundary)
    metric = gpd.GeoDataFrame(
        {"geometry": [expanded]}, geometry="geometry", crs="EPSG:4326"
    ).to_crs(metric_crs_for(gpd.GeoDataFrame(
        {"geometry": [boundary]}, geometry="geometry", crs="EPSG:4326")))
    assert metric.geometry.iloc[0].area > 0
