"""Shared geo helpers.

Locked decision: distance is geodesic, or computed in a projected CRS.
For Israel we reproject to ITM (EPSG:2039) and do meters math there —
never in WGS84 degrees.
"""

import geopandas as gpd

WGS84 = "EPSG:4326"
ISRAEL_TM = "EPSG:2039"  # Israeli Transverse Mercator — meters


def to_metric(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Reproject to a meters-based CRS for distance/buffer math."""
    return gdf.to_crs(ISRAEL_TM)


def to_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    return gdf.to_crs(WGS84)


def empty_features_gdf() -> gpd.GeoDataFrame:
    """An empty GeoDataFrame with a valid geometry column in WGS84."""
    return gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs=WGS84)
