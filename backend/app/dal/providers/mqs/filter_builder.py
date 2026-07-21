"""Build MQS filters and split dense geographic regions."""

from typing import List, Optional, Sequence, Tuple

from shapely.geometry import box
from shapely.geometry.base import BaseGeometry


class MqsFilterBuilder:
    def build(
        self,
        geometry: Optional[BaseGeometry],
        attribute_filters: Optional[Sequence[Tuple[str, str]]],
    ) -> Optional[dict]:
        if geometry is None and not attribute_filters:
            return None
        filters = {}
        if geometry is not None:
            filters["complex_operators"] = self._geometry(geometry)
        if attribute_filters:
            filters["simple_operators"] = self._attributes(attribute_filters)
        return {"filter": filters}

    def split(self, geometry: BaseGeometry) -> List[BaseGeometry]:
        min_x, min_y, max_x, max_y = geometry.bounds
        if min_x == max_x or min_y == max_y:
            return [geometry]
        cells = self._quadrants(min_x, min_y, max_x, max_y)
        chunks = [geometry.intersection(cell) for cell in cells]
        return [chunk for chunk in chunks if not chunk.is_empty and chunk.area > 0] or [geometry]

    def _geometry(self, geometry: BaseGeometry) -> dict:
        min_x, min_y, max_x, max_y = geometry.bounds
        if geometry.equals(box(min_x, min_y, max_x, max_y)):
            return self._bounding_box(min_x, min_y, max_x, max_y)
        return {"geo_polygon": {
            "geo": {"type": "IN", "values": [geometry.wkt]}
        }}

    @staticmethod
    def _bounding_box(min_x: float, min_y: float, max_x: float, max_y: float) -> dict:
        return {"geo_bounding_box": {"geo": {
            "type": "AND",
            "values": [{
                "location_top_left": {"lat": max_y, "lon": min_x},
                "location_bottom_right": {"lat": min_y, "lon": max_x},
            }],
        }}}

    @staticmethod
    def _attributes(filters: Sequence[Tuple[str, str]]) -> dict:
        match = {
            field: {"type": "IN", "values": [value]}
            for field, value in filters
        }
        return {"match": match}

    @staticmethod
    def _quadrants(min_x: float, min_y: float, max_x: float, max_y: float):
        middle_x = (min_x + max_x) / 2
        middle_y = (min_y + max_y) / 2
        return (
            box(min_x, min_y, middle_x, middle_y),
            box(middle_x, min_y, max_x, middle_y),
            box(min_x, middle_y, middle_x, max_y),
            box(middle_x, middle_y, max_x, max_y),
        )
