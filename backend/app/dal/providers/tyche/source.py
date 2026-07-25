"""Parse a catalog Tyche source into its route and field mapping."""

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, unquote, urlsplit

from app.common.errors.provider_error import ProviderError


@dataclass(frozen=True)
class TycheSource:
    route: str
    geometry_field: str
    geo_query_field: str
    time_field: str
    entity_field: Optional[str]
    time_from_field: Optional[str]
    time_to_field: Optional[str]
    parameters: Dict[str, Any]

    DEFAULT_GEOMETRY_FIELD = "geometry"
    DEFAULT_GEO_QUERY_FIELD = "location"
    DEFAULT_TIME_FIELD = "eventTime"
    DEFAULT_ENTITY_FIELD = "netId"
    _PARAMETER_PREFIX = "param_"
    _MAX_PARAMETERS = 50
    _ROUTE_PREFIX = "/coordinate/v1/"

    @classmethod
    def parse(cls, source_url: str) -> "TycheSource":
        parsed = urlsplit(source_url.strip())
        if parsed.scheme.casefold() != "tyche":
            raise ProviderError("Tyche source_url must use the tyche:// scheme")
        route = cls._route(parsed.netloc, parsed.path)
        query = parse_qs(parsed.query, keep_blank_values=True)
        source = cls._from_query(route, query)
        source._validate_query_fields()
        return source

    @classmethod
    def _from_query(cls, route: str, query: dict) -> "TycheSource":
        entity_default = (
            cls.DEFAULT_ENTITY_FIELD
            if route == cls._ROUTE_PREFIX + "ourforces" else None
        )
        return cls(
            route=route,
            geometry_field=cls._field(
                query, "geometry_field", cls.DEFAULT_GEOMETRY_FIELD
            ),
            geo_query_field=cls._field(
                query, "geo_query_field", cls.DEFAULT_GEO_QUERY_FIELD
            ),
            time_field=cls._field(query, "time_field", cls.DEFAULT_TIME_FIELD),
            entity_field=cls._optional_field(
                query, "entity_field", entity_default
            ),
            time_from_field=cls._optional_field(query, "time_from_field", None),
            time_to_field=cls._optional_field(query, "time_to_field", None),
            parameters=cls._parameters(query),
        )

    @classmethod
    def _route(cls, host: str, path: str) -> str:
        value = unquote(
            "/".join(part.strip("/") for part in (host, path) if part.strip("/"))
        )
        value = value.strip("/")
        if not value or ".." in value.split("/") or "\\" in value:
            raise ProviderError("Tyche source_url must contain a valid route")
        if "/" not in value:
            return cls._ROUTE_PREFIX + value
        return "/" + value

    @staticmethod
    def _field(query: dict, name: str, default: str) -> str:
        value = query.get(name, [default])[-1].strip()
        if not value or len(value) > 200 or any(ord(char) < 32 for char in value):
            raise ProviderError(f"Tyche {name} must be a valid field name")
        return value

    @classmethod
    def _optional_field(
        cls, query: dict, name: str, default: Optional[str]
    ) -> Optional[str]:
        if name not in query:
            return default
        value = query[name][-1].strip()
        return cls._field(query, name, value) if value else None

    @classmethod
    def _parameters(cls, query: dict) -> Dict[str, Any]:
        items = {
            key[len(cls._PARAMETER_PREFIX):]: cls._parameter_value(values[-1])
            for key, values in query.items()
            if key.startswith(cls._PARAMETER_PREFIX)
        }
        if len(items) > cls._MAX_PARAMETERS:
            raise ProviderError("Tyche supports at most 50 configured parameters")
        for name, value in items.items():
            cls._field({name: [name]}, name, name)
            if value == "":
                raise ProviderError(f"Tyche parameter '{name}' cannot be blank")
        return items

    @staticmethod
    def _parameter_value(value: str) -> Any:
        cleaned = value.strip()
        try:
            return json.loads(cleaned)
        except (TypeError, ValueError):
            return cleaned

    def _validate_query_fields(self) -> None:
        reserved = {"size", "fetchPaging", "pageTracker"}
        time_fields = self._request_time_fields()
        fields = {self.geo_query_field, self.time_field, *time_fields}
        if len(fields) != 2 + len(time_fields) or fields & reserved:
            raise ProviderError(
                "Tyche geography and time fields must be distinct "
                "and cannot use paging field names"
            )
        if set(self.parameters) & (fields | reserved):
            raise ProviderError(
                "Tyche configured parameters cannot replace time, geography, "
                "or paging fields"
            )
        if self.entity_field in reserved or self.entity_field in fields:
            raise ProviderError(
                "Tyche entity field must differ from time and paging fields"
            )

    def _request_time_fields(self):
        if bool(self.time_from_field) != bool(self.time_to_field):
            raise ProviderError(
                "Tyche timeFrom and timeTo fields must be configured together"
            )
        return {
            field for field in (self.time_from_field, self.time_to_field) if field
        }

    @property
    def is_our_forces(self) -> bool:
        return (
            self.route == self._ROUTE_PREFIX + "ourforces"
            and self.geometry_field == self.DEFAULT_GEOMETRY_FIELD
            and self.geo_query_field == self.DEFAULT_GEO_QUERY_FIELD
            and self.time_field == self.DEFAULT_TIME_FIELD
            and self.entity_field == self.DEFAULT_ENTITY_FIELD
            and not self.time_from_field
            and not self.time_to_field
            and not self.parameters
        )
