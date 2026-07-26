"""GeoDataFrame-to-GeoJSON translation."""

from typing import Any, Dict, Optional

import geopandas as gpd


def gdf_to_feature_collection(
    gdf: Optional[gpd.GeoDataFrame],
) -> Optional[Dict[str, Any]]:
    if gdf is None:
        return None
    if gdf.empty:
        return {"type": "FeatureCollection", "features": []}
    return gdf.__geo_interface__
