from typing import Any, Dict, Optional

import geopandas as gpd


class FeatureCollectionMapper:
    @staticmethod
    def from_gdf(
        gdf: Optional[gpd.GeoDataFrame],
    ) -> Optional[Dict[str, Any]]:
        if gdf is None:
            return None
        if gdf.empty:
            return {"type": "FeatureCollection", "features": []}
        return gdf.__geo_interface__


gdf_to_feature_collection = FeatureCollectionMapper.from_gdf
