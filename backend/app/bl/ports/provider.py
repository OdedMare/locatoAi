from datetime import datetime
from typing import List, Optional, Protocol, Tuple

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

from app.bl.ports.layer_meta import LayerMeta
from app.bl.ports.layer_schema import LayerSchema


class Provider(Protocol):
    """A GIS data provider (implemented by dal.providers.*).

    ISP: this is intentionally the whole surface — describe and fetch.
    """

    def describe_schema(self, layer: LayerMeta) -> LayerSchema: ...

    def fetch_features(
        self,
        layer: LayerMeta,
        now: Optional[datetime] = None,
        geometry: Optional[BaseGeometry] = None,
        limit: Optional[int] = None,
        temporal_range: Optional[Tuple[str, str]] = None,
    ) -> gpd.GeoDataFrame:
        """geometry, when given, is a WGS84 hint the provider MAY push down
        as a server-side spatial filter (e.g. MQS geo_polygon/
        geo_bounding_box) to avoid fetching the whole layer. It is always
        an optimization: within_geometry still re-filters client-side
        (correctness doesn't depend on any provider honoring this).

        limit, when given, caps how many features the provider needs to
        return (e.g. for a metadata/tagging sample) — providers MAY stop
        paginating early rather than fetching the whole layer. Callers
        that pass a limit must not assume ordering or completeness."""
        ...

    def sample_field_values(
        self, layer: LayerMeta, field: str, limit: int = 20
    ) -> List[str]:
        """Distinct example values of one field — backs the plan agent's
        on-demand sample_field tool. Values are untrusted text."""
        ...
