from datetime import datetime
from typing import FrozenSet, List, Optional, Protocol, Tuple

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

from app.bl.catalog.models.layer_meta import LayerMeta
from app.bl.catalog.models.layer_schema import LayerSchema

TEMPORAL_PUSHDOWN = "temporal_range"
ATTRIBUTE_FILTER_PUSHDOWN = "attribute_filters"


class Provider(Protocol):
    """A GIS data provider (implemented by dal.providers.*).

    ISP: this is intentionally the whole surface — describe and fetch.
    """

    capabilities: FrozenSet[str]

    def describe_schema(self, layer: LayerMeta) -> LayerSchema: ...

    def fetch_features(
        self,
        layer: LayerMeta,
        now: Optional[datetime] = None,
        geometry: Optional[BaseGeometry] = None,
        limit: Optional[int] = None,
        attribute_filters: Optional[List[Tuple[str, str]]] = None,
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
        that pass a limit must not assume ordering or completeness.

        attribute_filters, when given, is a list of (field, value) equality
        pairs the provider MAY push down as a server-side attribute filter
        (e.g. MQS simple_operators.match), ANDed together. It is always an
        optimization: attribute_filter still re-filters client-side
        (correctness doesn't depend on any provider honoring this).

        temporal_range follows the same rule: capable providers may push it
        down, while temporal_filter still re-applies it client-side."""
        ...

    def sample_field_values(
        self, layer: LayerMeta, field: str, limit: int = 20
    ) -> List[str]:
        """Distinct example values of one field — backs the plan agent's
        on-demand sample_field tool. Values are untrusted text."""
        ...
