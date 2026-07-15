from typing import Any, Dict, Optional

import geopandas as gpd


def gdf_to_feature_collection(
    gdf: Optional[gpd.GeoDataFrame],
) -> Optional[Dict[str, Any]]:
    """Every GeoDataFrame column becomes a GeoJSON `properties` field
    automatically — ops that compute extra per-feature attributes (e.g.
    NearOp's `distance_to_target_m`, ops/near.py) need no DTO change,
    they just add a column."""
    if gdf is None:
        return None
    if gdf.empty:
        return {"type": "FeatureCollection", "features": []}
    return gdf.__geo_interface__
