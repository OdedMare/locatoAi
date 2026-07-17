"""Construct Cubes request bodies and split saturated query regions."""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from shapely.geometry import box
from shapely.geometry.base import BaseGeometry

from app.bl.ports.layer_parameter import LayerParameter
from app.common.errors.provider_error import ProviderError


class CubesQueryBuilder:
    _TIME_FIELDS = ("eventTime", "arriveTime", "timestamp", "time", "datetime")
    _OPERATORS = ("match", "not")
    _DEFAULT_KEYS = (
        "eventTime", "eventTime.not", "arriveTime", "arriveTime.not",
    )

    def build(
        self,
        geometry: Optional[BaseGeometry],
        parameters: Optional[List[LayerParameter]] = None,
        now: Optional[datetime] = None,
        temporal_range=None,
        query_mode: str = "auto",
    ) -> dict:
        parameters = parameters or []
        keys = self._query_keys(parameters, query_mode)
        body = {
            key: self._parameter_value(key, now, temporal_range)
            for key in keys if self.parts(key)[0] in self._TIME_FIELDS
        }
        self._apply_configured(parameters, body)
        self._validate_required(parameters, body)
        self._add_location(body, geometry)
        return body

    def resolve_dynamic(
        self, parameters: List[LayerParameter], resolved: Dict[str, str]
    ) -> List[LayerParameter]:
        configured = [self._with_resolved(item, resolved) for item in parameters]
        configured_names = {item.name for item in parameters}
        configured.extend(
            LayerParameter(
                name=name, type="string", is_dynamic=True, resolved_value=value
            )
            for name, value in resolved.items()
            if name not in configured_names
        )
        return configured

    def match_window_key(self, body: dict) -> Optional[str]:
        return next((key for key in body if self.parts(key)[1] == "match"), None)

    def split_temporal_range(
        self, from_iso: str, to_iso: str
    ) -> List[Tuple[str, str]]:
        start = datetime.fromisoformat(from_iso.replace("Z", "+00:00"))
        end = datetime.fromisoformat(to_iso.replace("Z", "+00:00"))
        middle = start + (end - start) / 2
        middle_iso = self._iso_milliseconds(middle)
        return [(from_iso, middle_iso), (middle_iso, to_iso)]

    @staticmethod
    def spatial_chunks(geometry: BaseGeometry) -> List[BaseGeometry]:
        min_x, min_y, max_x, max_y = geometry.bounds
        middle_x = (min_x + max_x) / 2
        middle_y = (min_y + max_y) / 2
        tiles = (
            box(min_x, min_y, middle_x, middle_y),
            box(middle_x, min_y, max_x, middle_y),
            box(min_x, middle_y, middle_x, max_y),
            box(middle_x, middle_y, max_x, max_y),
        )
        return [part for tile in tiles for part in [geometry.intersection(tile)]
                if not part.is_empty and part.area > 0]

    def _query_keys(
        self, parameters: List[LayerParameter], query_mode: str
    ) -> List[str]:
        if query_mode == "match_not":
            return ["eventTime.match", "eventTime.not"]
        if query_mode == "legacy":
            return list(self._DEFAULT_KEYS)
        return self._declared_keys(parameters) if parameters else list(self._DEFAULT_KEYS)

    def _declared_keys(self, parameters: List[LayerParameter]) -> List[str]:
        keys: List[str] = []
        for parameter in parameters:
            base, operator = self.parts(parameter.name)
            for item in ((operator,) if operator else (None, "not")):
                key = self._key(base, item)
                if key not in keys:
                    keys.append(key)
        return keys

    @staticmethod
    def parts(name: str) -> Tuple[str, Optional[str]]:
        base, separator, operator = name.rpartition(".")
        if separator and operator.lower() in CubesQueryBuilder._OPERATORS:
            return base, operator.lower()
        return name, None

    @staticmethod
    def _key(base: str, operator: Optional[str]) -> str:
        return base if operator is None else f"{base}.{operator}"

    def _parameter_value(self, key: str, now, temporal_range) -> dict:
        base, operator = self.parts(key)
        if operator == "match":
            return self._absolute_window(now, temporal_range)
        unit = "no_time" if base == "arriveTime" and operator is None else "hour"
        return {"TimeBackValue": "1", "TimeBackUnit": unit}

    def _absolute_window(self, now, temporal_range) -> dict:
        if temporal_range is not None:
            return {"From": temporal_range[0], "To": temporal_range[1]}
        end = now or datetime.now(timezone.utc)
        return {
            "From": self._iso_milliseconds(end - timedelta(hours=1)),
            "To": self._iso_milliseconds(end),
        }

    @staticmethod
    def _iso_milliseconds(value: datetime) -> str:
        normalized = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return normalized.astimezone(timezone.utc).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z")

    @staticmethod
    def _apply_configured(parameters: List[LayerParameter], body: dict) -> None:
        for parameter in parameters:
            if parameter.is_dynamic and parameter.resolved_value is not None:
                body[parameter.name] = parameter.resolved_value
            elif parameter.configured_value not in (None, ""):
                body.setdefault(parameter.name, parameter.configured_value)

    def _validate_required(self, parameters: List[LayerParameter], body: dict) -> None:
        for parameter in parameters:
            base, operator = self.parts(parameter.name)
            configured = operator is None and any(
                self.parts(body_key)[0] == base for body_key in body
            )
            if parameter.required and self._key(base, operator) not in body and not configured:
                raise ProviderError(
                    f"Cubes parameter '{parameter.name}' is required and has no configured value"
                )

    def _add_location(
        self, body: dict, geometry: Optional[BaseGeometry]
    ) -> None:
        if geometry is None:
            return
        location_key = self._location_key(body)
        if location_key is not None:
            body[location_key]["Location"] = geometry.wkt

    def _location_key(self, body: dict) -> Optional[str]:
        for key in ("arriveTime.not", "eventTime.not"):
            if key in body:
                return key
        return next((key for key in body if self.parts(key)[0] in self._TIME_FIELDS), None)

    @staticmethod
    def _with_resolved(
        parameter: LayerParameter, resolved: Dict[str, str]
    ) -> LayerParameter:
        if parameter.name not in resolved:
            return parameter
        return parameter.model_copy(update={
            "is_dynamic": True,
            "resolved_value": resolved[parameter.name],
        })
