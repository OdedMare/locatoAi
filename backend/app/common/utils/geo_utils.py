"""Shared CRS helpers for safe spatial calculations."""

import geopandas as gpd
from typing import Optional
from pyproj import CRS
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

WGS84 = "EPSG:4326"
ISRAEL_TM = "EPSG:2039"  # Israeli Transverse Mercator — meters
WEB_MERCATOR = "EPSG:3857"


class GeoUtils:
    @staticmethod
    def require_crs(gdf: gpd.GeoDataFrame, operation: str) -> None:
        if gdf.crs is None:
            raise ValueError(f"{operation}: input features have no CRS")

    @classmethod
    def metric_crs_for(cls, *frames: gpd.GeoDataFrame) -> CRS:
        usable = [frame for frame in frames if not frame.empty]
        if not usable:
            return CRS.from_user_input(WEB_MERCATOR)
        for frame in usable:
            cls.require_crs(frame, "metric projection")
        bounds = [frame.to_crs(WGS84).total_bounds for frame in usable]
        center = cls._center(bounds)
        return center.estimate_utm_crs() or CRS.from_user_input(WEB_MERCATOR)

    @staticmethod
    def _center(bounds) -> gpd.GeoSeries:
        min_x = min(bound[0] for bound in bounds)
        min_y = min(bound[1] for bound in bounds)
        max_x = max(bound[2] for bound in bounds)
        max_y = max(bound[3] for bound in bounds)
        point = Point((min_x + max_x) / 2, (min_y + max_y) / 2)
        return gpd.GeoSeries([point], crs=WGS84)

    @classmethod
    def to_metric(
        cls, gdf: gpd.GeoDataFrame, crs: Optional[CRS] = None
    ) -> gpd.GeoDataFrame:
        cls.require_crs(gdf, "metric projection")
        return gdf.to_crs(crs or cls.metric_crs_for(gdf))

    @staticmethod
    def to_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        return gdf.to_crs(WGS84)

    @classmethod
    def buffer_wgs84_geometry(
        cls, geometry: BaseGeometry, distance_m: float
    ) -> BaseGeometry:
        frame = gpd.GeoDataFrame(
            {"geometry": [geometry]}, geometry="geometry", crs=WGS84
        )
        metric_crs = cls.metric_crs_for(frame)
        buffered = frame.to_crs(metric_crs).geometry.buffer(distance_m)
        return gpd.GeoSeries(buffered, crs=metric_crs).to_crs(WGS84).iloc[0]

    @staticmethod
    def empty_features_gdf() -> gpd.GeoDataFrame:
        return gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs=WGS84)


require_crs = GeoUtils.require_crs
metric_crs_for = GeoUtils.metric_crs_for
to_metric = GeoUtils.to_metric
to_wgs84 = GeoUtils.to_wgs84
buffer_wgs84_geometry = GeoUtils.buffer_wgs84_geometry
empty_features_gdf = GeoUtils.empty_features_gdf
