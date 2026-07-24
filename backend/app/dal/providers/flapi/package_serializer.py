"""Serialize and validate Flow Package inputs."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from shapely import wkt
from shapely.geometry.base import BaseGeometry

from app.common.errors.provider_error import ProviderError
from app.dal.providers.flapi.package_metadata import FlowPackageMetadata


class FlowPackageSerializer:
    _TIME_UNITS = {"minute", "hour", "day", "week", "month"}
    _NUMBER_TYPES = {"number", "numeric", "integer", "int", "float", "double"}
    _TEXT_TYPES = {"string", "text"}
    _BOOLEAN_TYPES = {"bool", "boolean"}

    def __init__(self, metadata: FlowPackageMetadata) -> None:
        self._metadata = metadata

    def build(
        self,
        definitions: List[dict],
        configured: Dict[str, Any],
        geometry: Optional[BaseGeometry] = None,
        temporal_range: Optional[Tuple[str, str]] = None,
    ) -> dict:
        body = {}
        for item in definitions:
            name = str(self._metadata.value(item, "Name", "name"))
            value = self._value(
                item, configured, geometry, temporal_range
            )
            if value is not None:
                body[name] = self._serialize(item, value)
            elif self._metadata.bool_value(
                item, False, "IsRequired", "isRequired"
            ):
                raise ProviderError(
                    f"Flow Package parameter '{name}' is required"
                )
        return body

    def _value(self, item, configured, geometry, temporal_range):
        name = str(self._metadata.value(item, "Name", "name"))
        if self._metadata.is_geometry(item) and geometry is not None:
            return {"value": geometry.wkt}
        if self._metadata.is_time(item) and temporal_range is not None:
            return {"From": temporal_range[0], "To": temporal_range[1]}
        if name in configured:
            return configured[name]
        return self._metadata.value(item, "Value", "value")

    def _serialize(self, item: dict, raw: Any) -> Any:
        value = self._decode_json(raw)
        if self._metadata.is_geometry(item):
            return self._geometry(value)
        if self._metadata.is_time(item):
            return self._time(value)
        kind = str(self._metadata.value(item, "Type", "type") or "").casefold()
        if kind in self._BOOLEAN_TYPES:
            return value
        single = self._metadata.bool_value(
            item, True, "IsSingleValue", "isSingleValue"
        )
        if kind in self._NUMBER_TYPES:
            return self._single(self._number(value)) if single else self._multi(
                value, numeric=True
            )
        if kind in self._TEXT_TYPES:
            return self._single(value) if single else self._multi(value)
        return value  # unknown types are passed through unchanged

    def _geometry(self, raw: Any) -> dict:
        value = raw.get("value") if isinstance(raw, dict) else raw
        if not isinstance(value, str):
            raise ProviderError("Flow Package geometry must be WKT text")
        try:
            geometry = wkt.loads(value)
        except Exception as exc:
            raise ProviderError("Flow Package geometry contains invalid WKT") from exc
        if geometry.is_empty:
            raise ProviderError("Flow Package geometry cannot be empty")
        return {"value": value}

    def _time(self, raw: Any) -> dict:
        if not isinstance(raw, dict):
            raise ProviderError("Flow Package time parameter must be a JSON object")
        if "TimeBackUnit" in raw or "TimeBackValue" in raw:
            return self._relative_time(raw)
        if "From" in raw or "To" in raw:
            return self._absolute_time(raw)
        raise ProviderError(
            "Flow Package time needs TimeBackUnit/TimeBackValue or From/To"
        )

    def _relative_time(self, raw: dict) -> dict:
        unit, value = raw.get("TimeBackUnit"), raw.get("TimeBackValue")
        if unit not in self._TIME_UNITS:
            raise ProviderError(f"Unsupported Flow Package time unit '{unit}'")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            raise ProviderError("Flow Package TimeBackValue must be a positive number")
        return {"TimeBackUnit": unit, "TimeBackValue": value}

    def _absolute_time(self, raw: dict) -> dict:
        start, end = raw.get("From"), raw.get("To")
        self._iso_timestamp(start, "From")
        self._iso_timestamp(end, "To")
        return {"From": start, "To": end}

    @staticmethod
    def _iso_timestamp(value: Any, field: str) -> None:
        if not isinstance(value, str):
            raise ProviderError(f"Flow Package time {field} must be ISO 8601")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ProviderError(
                f"Flow Package time {field} must be ISO 8601"
            ) from exc
        if parsed.tzinfo is None:
            raise ProviderError(
                f"Flow Package time {field} must include a timezone"
            )

    def _multi(self, raw: Any, numeric: bool = False) -> List[dict]:
        values = raw if isinstance(raw, list) else [
            value.strip() for value in str(raw).split(",") if value.strip()
        ]
        result = []
        for value in values:
            if isinstance(value, dict) and "Value" in value:
                result.append(self._number(value) if numeric else value)
                continue
            actual = self._number(value) if numeric else value
            result.append({"Name": str(actual), "Value": actual})
        return result

    @staticmethod
    def _single(raw: Any) -> dict:
        if isinstance(raw, dict) and "Value" in raw:
            return raw
        return {"Name": str(raw), "Value": raw}

    @staticmethod
    def _number(raw: Any) -> Any:
        if isinstance(raw, dict) and "Value" in raw:
            value = FlowPackageSerializer._number(raw["Value"])
            return {"Name": str(raw.get("Name", value)), "Value": value}
        if isinstance(raw, bool):
            raise ProviderError("Flow Package numeric value cannot be boolean")
        if isinstance(raw, (int, float)):
            return raw
        try:
            text = str(raw).strip()
            return float(text) if any(char in text for char in ".eE") else int(text)
        except (TypeError, ValueError) as exc:
            raise ProviderError("Flow Package numeric value is invalid") from exc

    @staticmethod
    def _decode_json(raw: Any) -> Any:
        if not isinstance(raw, str):
            return raw
        text = raw.strip()
        if not text or text[0] not in "[{":
            return raw
        try:
            return json.loads(text)
        except ValueError:
            return raw
