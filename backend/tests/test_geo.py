import geopandas as gpd
from shapely.geometry import Point

from app.common.geo import metric_crs_for, to_metric


def test_metric_crs_is_estimated_for_data_location_not_fixed_to_israel():
    los_angeles = gpd.GeoDataFrame(
        {"geometry": [Point(-118.4912, 33.9850)]}, crs="EPSG:4326"
    )
    crs = metric_crs_for(los_angeles)

    assert crs.to_epsg() == 32611
    projected = to_metric(los_angeles, crs)
    assert projected.crs.to_epsg() == 32611
