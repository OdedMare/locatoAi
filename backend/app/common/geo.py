"""Shared CRS helpers for safe spatial calculations."""

import geopandas as gpd
from typing import Optional
from pyproj import CRS
from shapely.geometry import Point

WGS84 = "EPSG:4326"
ISRAEL_TM = "EPSG:2039"  # Israeli Transverse Mercator — meters
WEB_MERCATOR = "EPSG:3857"


def require_crs(gdf: gpd.GeoDataFrame, operation: str) -> None:
    """Fail loudly rather than interpreting unknown coordinates as WGS84."""
    if gdf.crs is None:
        raise ValueError(f"{operation}: input features have no CRS")


def metric_crs_for(*frames: gpd.GeoDataFrame) -> CRS:
    """Choose one local meters-based CRS shared by all input frames.

    A fixed Israeli projection is accurate locally but badly wrong for data
    such as Venice Beach. A UTM zone estimated from the combined WGS84 extent
    gives reliable local distance calculations anywhere UTM is defined.
    """
    usable = [frame for frame in frames if not frame.empty]
    if not usable:
        return CRS.from_user_input(WEB_MERCATOR)
    for frame in usable:
        require_crs(frame, "metric projection")
    bounds = [frame.to_crs(WGS84).total_bounds for frame in usable]
    minx = min(bound[0] for bound in bounds)
    miny = min(bound[1] for bound in bounds)
    maxx = max(bound[2] for bound in bounds)
    maxy = max(bound[3] for bound in bounds)
    center = gpd.GeoSeries(
        [Point((minx + maxx) / 2, (miny + maxy) / 2)], crs=WGS84
    )
    estimated = center.estimate_utm_crs()
    return estimated or CRS.from_user_input(WEB_MERCATOR)


def to_metric(
    gdf: gpd.GeoDataFrame, crs: Optional[CRS] = None
) -> gpd.GeoDataFrame:
    """Reproject to a suitable meters-based CRS for distance/buffer math."""
    require_crs(gdf, "metric projection")
    return gdf.to_crs(crs or metric_crs_for(gdf))


def to_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    return gdf.to_crs(WGS84)


def empty_features_gdf() -> gpd.GeoDataFrame:
    """An empty GeoDataFrame with a valid geometry column in WGS84."""
    return gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs=WGS84)
