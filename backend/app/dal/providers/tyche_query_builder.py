"""Build Tyche request bodies from provider inputs."""

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

from shapely.geometry.base import BaseGeometry

from app.common.errors.provider_error import ProviderError


class TycheQueryBuilder:
    _DEFAULT_LOOKBACK = timedelta(hours=1)

    def build(
        self,
        now: Optional[datetime],
        geometry: Optional[BaseGeometry],
        temporal_range: Optional[Tuple[str, str]],
        size: int,
        page_tracker: Optional[str] = None,
    ) -> dict:
        body = self._base_body(now, temporal_range, size)
        if geometry is not None:
            body["location"] = {"match": geometry.wkt}
        if page_tracker:
            body["pageTracker"] = page_tracker
        return body

    def _base_body(
        self,
        now: Optional[datetime],
        temporal_range: Optional[Tuple[str, str]],
        size: int,
    ) -> dict:
        return {
            "eventTime": {"match": self._time_window(now, temporal_range)},
            "size": size,
            "fetchPaging": True,
        }

    def _time_window(
        self,
        now: Optional[datetime],
        temporal_range: Optional[Tuple[str, str]],
    ) -> Dict[str, str]:
        start, end = self._bounds(now, temporal_range)
        if start > end:
            raise ProviderError("Tyche temporal range starts after it ends")
        return {"gte": self._format(start), "lte": self._format(end)}

    def _bounds(
        self,
        now: Optional[datetime],
        temporal_range: Optional[Tuple[str, str]],
    ) -> Tuple[datetime, datetime]:
        if temporal_range is not None:
            return tuple(self._parse(value) for value in temporal_range)
        end = self._as_utc(now or datetime.now(timezone.utc))
        return end - self._DEFAULT_LOOKBACK, end

    def _parse(self, value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except (AttributeError, ValueError) as exc:
            raise ProviderError(
                f"Tyche received an invalid temporal bound: {value}"
            ) from exc
        return self._as_utc(parsed)

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

    def _format(self, value: datetime) -> str:
        return self._as_utc(value).astimezone(timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S.%f"
        )[:-3]
