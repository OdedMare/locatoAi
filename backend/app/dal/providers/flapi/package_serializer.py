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
        self, input_cube_name: Optional[str],
        input_cube_parameter: Optional[str], kind: str = "time",
        temporal_range: Optional[Tuple[str, str]] = None,
        geometry: Optional[BaseGeometry] = None, now: Optional[datetime] = None,
    ) -> PackageInputCube:
        self._log_build(
            kind, input_cube_name, input_cube_parameter, temporal_range, geometry
        )
        self._validate_names(input_cube_name, input_cube_parameter)
        cube = self._cube(
            kind, input_cube_name, input_cube_parameter,
            temporal_range, geometry, now,
        )
        self._logger.info(
            "FLAPI input cube READY %s", FlowPackageDebug.input_cube(cube)
        )
        return cube

    def _log_build(self, kind, name, parameter, temporal_range, geometry):
        self._logger.info(
            "FLAPI input cube BUILD kind=%s cube_name=%r parameter=%r "
            "temporal_range=%s %s",
            kind, name, parameter, temporal_range,
            FlowPackageDebug.geometry(geometry),
        )

    def _cube(self, kind, name, parameter, temporal_range, geometry, now):
        if kind == "geo":
            return self._geo_cube(name, parameter, geometry)
        return self._time_cube(
            name, parameter, temporal_range, now
        )

    @staticmethod
    def _validate_names(name: Optional[str], parameter: Optional[str]) -> None:
        if not name:
            raise ProviderError("Flow Package input cube name is required")
        if not parameter:
            raise ProviderError("Flow Package input cube parameter is required")

    def _geo_cube(self, name, parameter, geometry):
        return PackageInputCube(
            cube_name=name,
            cube_parameter=parameter,
            values=self._multipolygons(geometry),
        )

    def _time_cube(self, name, parameter, temporal_range, now):
        start, end = self._range(temporal_range, now)
        return PackageInputCube(
            cube_name=name, cube_parameter=parameter,
            start_time=start, end_time=end,
        )

    def _multipolygons(self, geometry: Optional[BaseGeometry]) -> List[str]:
        if geometry is None or geometry.is_empty:
            raise ProviderError(
                "Flow Package geographic input requires a query boundary — "
                "draw a polygon or use the viewport"
            )
        parts = getattr(geometry, "geoms", None)
        polygons = list(parts) if parts is not None else [geometry]
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
