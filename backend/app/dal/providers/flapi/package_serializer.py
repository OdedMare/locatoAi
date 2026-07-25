"""Build the flunks input cube from configured cube names and a time range."""

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from flunks import PackageInputCube

from app.common.errors.provider_error import ProviderError


class FlowPackageSerializer:
    """Assembles a time-range `PackageInputCube` from the configured cube names.

    Per the flunks Package API the input cube is driven by a single time-range
    parameter (``cube_parameter``) receiving ``start_time``/``end_time``. Every
    other package parameter is fixed inside the package itself, so nothing else
    is serialized here.
    """

    _SAMPLE_WINDOW = timedelta(hours=1)

    def build_input_cube(
        self,
        input_cube_name: Optional[str],
        input_cube_parameter: Optional[str],
        temporal_range: Optional[Tuple[str, str]] = None,
        now: Optional[datetime] = None,
    ) -> PackageInputCube:
        if not input_cube_name:
            raise ProviderError("Flow Package input cube name is required")
        if not input_cube_parameter:
            raise ProviderError("Flow Package input cube parameter is required")
        start, end = self._range(temporal_range, now)
        return PackageInputCube(
            cube_name=input_cube_name,
            cube_parameter=input_cube_parameter,
            start_time=start,
            end_time=end,
        )

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
