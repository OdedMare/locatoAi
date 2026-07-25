"""Build the flunks input cube from configured cube names and query inputs."""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from flunks import PackageInputCube
from shapely.geometry import MultiPolygon
from shapely.geometry.base import BaseGeometry

from app.common.errors.provider_error import ProviderError
from app.dal.providers.flapi.package_debug import FlowPackageDebug


class FlowPackageSerializer:
    """Assembles the flunks input cube from the configured cube names.

    The input cube is driven by a single ``cube_parameter`` whose values come
    from the query. Two kinds are supported:

    - ``geo``  — the query boundary is passed via ``values`` as a single-element
      list holding one WKT multipolygon containing every boundary polygon.
    - ``time`` — the query time range is passed as ``start_time``/``end_time``.

    Every other package parameter is fixed inside the package itself, so
    nothing else is serialized here.
    """

    _SAMPLE_WINDOW = timedelta(hours=1)

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def build_input_cube(
        self,
        input_cube_name: Optional[str],
        input_cube_parameter: Optional[str],
        kind: str = "time",
        temporal_range: Optional[Tuple[str, str]] = None,
        geometry: Optional[BaseGeometry] = None,
        now: Optional[datetime] = None,
    ) -> PackageInputCube:
        self._logger.info(
            "FLAPI input cube BUILD kind=%s cube_name=%r parameter=%r "
            "temporal_range=%s %s",
            kind, input_cube_name, input_cube_parameter, temporal_range,
            FlowPackageDebug.geometry(geometry),
        )
        if not input_cube_name:
            raise ProviderError("Flow Package input cube name is required")
        if not input_cube_parameter:
            raise ProviderError("Flow Package input cube parameter is required")
        if kind == "geo":
            cube = PackageInputCube(
                cube_name=input_cube_name,
                cube_parameter=input_cube_parameter,
                values=self._multipolygons(geometry),
            )
        else:
            start, end = self._range(temporal_range, now)
            cube = PackageInputCube(
                cube_name=input_cube_name,
                cube_parameter=input_cube_parameter,
                start_time=start,
                end_time=end,
            )
        self._logger.info(
            "FLAPI input cube READY %s", FlowPackageDebug.input_cube(cube)
        )
        return cube

    def _multipolygons(self, geometry: Optional[BaseGeometry]) -> List[str]:
        # FLAPI rejects an empty main cube input ("Please enter values for the
        # main cube input"), so there is no useful no-geometry fallback here —
        # say which layer configuration is at fault instead.
        if geometry is None or geometry.is_empty:
            raise ProviderError(
                "Flow Package geographic input requires a query boundary — "
                "draw a polygon or use the viewport"
            )
        parts = getattr(geometry, "geoms", None)
        polygons = list(parts) if parts is not None else [geometry]
        # One geographic layer is one identifier: every boundary polygon goes
        # into a single MULTIPOLYGON so the package runs as one chunk.
        return [MultiPolygon(polygons).wkt]

    def _range(
        self,
        temporal_range: Optional[Tuple[str, str]],
        now: Optional[datetime],
    ) -> Tuple[datetime, datetime]:
        if temporal_range is not None:
            return self._parse_iso(temporal_range[0]), self._parse_iso(
                temporal_range[1]
            )
        end = now or datetime.now(timezone.utc)
        return end - self._SAMPLE_WINDOW, end

    @staticmethod
    def _parse_iso(value: str) -> datetime:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ProviderError(
                "Flow Package temporal range must be ISO 8601"
            ) from exc
