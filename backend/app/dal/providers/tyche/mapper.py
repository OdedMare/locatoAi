"""Parse Tyche source/input and map Tyche output."""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlsplit

import geopandas as gpd
from shapely import wkt
from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry

from app.bl.catalog.models.layer_field import LayerField
from app.bl.catalog.models.layer_meta import LayerMeta
from app.bl.catalog.models.layer_schema import LayerSchema
from app.common.errors.provider_error import ProviderError
from app.common.utils.geo_utils import WGS84, empty_features_gdf


class TycheMapper:
    """Own every Tyche input/output shape; the provider only performs HTTP."""

    _ROUTE_PREFIX = "/coordinate/v1/"
    _DEFAULT_LOOKBACK = timedelta(hours=1)
    _DEFAULTS = {
        "geometry_field": "geometry",
        "geo_query_field": "location",
        "time_field": "eventTime",
    }
    _FIELDS = (
        ("eventTime", "date", "Event occurrence time"),
        ("arriveTime", "date", "Time the event arrived at the repository"),
        ("callSign", "string", "Force call sign"),
        ("forceType", "string", "Force type or reporting platform"),
        ("unit", "string", "Organizational unit"),
        ("netId", "string", "Force/network identifier"),
        ("pstn", "string", "Force telephone number"),
        ("sourceType", "string", "Report source"),
        ("id", "string", "Unique event identifier"),
        ("trigger", "string", "Event type or trigger"),
        ("locationType", "string", "Polygon/location type"),
    )

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def source(self, source_url: str) -> Dict[str, Any]:
        parsed = urlsplit(source_url.strip())
        if parsed.scheme.casefold() != "tyche":
            raise ProviderError("Tyche source_url must use the tyche:// scheme")
        route = self._route(parsed.netloc, parsed.path)
        query = parse_qs(parsed.query, keep_blank_values=True)
        source = self._source_fields(route, query)
        self._validate_source(source)
        source["is_our_forces"] = self._is_our_forces(source)
        return source

    def request(
        self, source: Dict[str, Any], now: Optional[datetime],
        geometry: Optional[BaseGeometry],
        temporal_range: Optional[Tuple[str, str]], size: int,
        page_tracker: Optional[str] = None,
    ) -> dict:
        body = dict(source["parameters"])
        body.update(self._time_body(source, now, temporal_range))
        body.update({"size": size, "fetchPaging": True})
        if geometry is not None:
            body[source["geo_query_field"]] = {"match": geometry.wkt}
        if page_tracker:
            body["pageTracker"] = page_tracker
        return body

    def to_gdf(
        self, rows: List[dict], geometry_field: str,
    ) -> gpd.GeoDataFrame:
        parsed = [(row, self._parse_geometry(row.get(geometry_field)))
                  for row in rows]
        valid = [(row, geometry) for row, geometry in parsed
                 if geometry is not None and not geometry.is_empty]
        if len(valid) != len(rows):
            self._logger.warning(
                "Tyche skipped %s rows with invalid geometry",
                len(rows) - len(valid),
            )
        return self._gdf(valid, geometry_field)

    def deduplicate(self, rows: List[dict]) -> List[dict]:
        unique: Dict[str, dict] = {}
        for row in rows:
            identifier = row.get("id")
            key = (
                "id:%s" % identifier if identifier is not None
                else json.dumps(row, ensure_ascii=False, sort_keys=True, default=str)
            )
            unique.setdefault(key, row)
        return list(unique.values())

    def schema(
        self, layer: LayerMeta, rows: List[dict], source: Dict[str, Any],
    ) -> LayerSchema:
        temporal = source["time_field"]
        definitions = (
            self._FIELDS if source["is_our_forces"]
            else ((temporal, "date", "Event occurrence time"),)
        )
        declared = [self._declared_field(item, rows) for item in definitions]
        fields = declared + self._extra_fields(
            declared, rows, source["geometry_field"], temporal,
        )
        return LayerSchema(
            layer_id=layer.id, geometry_type="Geometry", fields=fields,
            source_name="Our Forces" if source["is_our_forces"] else layer.name,
            source_description=("Tyche own-force events and geographic positions"
                                if source["is_our_forces"] else layer.description),
            entity_field=layer.entity_field or source["entity_field"],
            temporal_field=temporal, display_field=layer.display_field,
        )

    def _source_fields(self, route: str, query: dict) -> Dict[str, Any]:
        default_entity = "netId" if route == self._ROUTE_PREFIX + "ourforces" else None
        source = {
            key: self._field(query, key, default)
            for key, default in self._DEFAULTS.items()
        }
        source.update({
            "route": route,
            "entity_field": self._optional_field(
                query, "entity_field", default_entity),
            "time_from_field": self._optional_field(
                query, "time_from_field", None),
            "time_to_field": self._optional_field(
                query, "time_to_field", None),
            "parameters": self._parameters(query),
        })
        return source

    def _parameters(self, query: dict) -> Dict[str, Any]:
        items = {
            key[6:]: self._parameter_value(values[-1])
            for key, values in query.items() if key.startswith("param_")
        }
        if len(items) > 50:
            raise ProviderError("Tyche supports at most 50 configured parameters")
        for name, value in items.items():
            self._field({name: [name]}, name, name)
            if value == "":
                raise ProviderError("Tyche parameter '%s' cannot be blank" % name)
        return items

    def _validate_source(self, source: Dict[str, Any]) -> None:
        reserved = {"size", "fetchPaging", "pageTracker"}
        time_fields = self._request_time_fields(source)
        fields = {
            source["geo_query_field"], source["time_field"], *time_fields,
        }
        if len(fields) != 2 + len(time_fields) or fields & reserved:
            raise ProviderError(
                "Tyche geography and time fields must be distinct "
                "and cannot use paging field names"
            )
        if set(source["parameters"]) & (fields | reserved):
            raise ProviderError(
                "Tyche configured parameters cannot replace time, geography, "
                "or paging fields"
            )
        if source["entity_field"] in reserved or source["entity_field"] in fields:
            raise ProviderError(
                "Tyche entity field must differ from time and paging fields"
            )

    @staticmethod
    def _request_time_fields(source: Dict[str, Any]) -> set:
        start, end = source["time_from_field"], source["time_to_field"]
        if bool(start) != bool(end):
            raise ProviderError(
                "Tyche timeFrom and timeTo fields must be configured together"
            )
        if start and start == end:
            raise ProviderError(
                "Tyche timeFrom and timeTo fields must be distinct"
            )
        return {field for field in (start, end) if field}

    def _is_our_forces(self, source: Dict[str, Any]) -> bool:
        return (
            source["route"] == self._ROUTE_PREFIX + "ourforces"
            and all(source[key] == value for key, value in self._DEFAULTS.items())
            and source["entity_field"] == "netId"
            and not source["time_from_field"] and not source["time_to_field"]
            and not source["parameters"]
        )

    @classmethod
    def _route(cls, host: str, path: str) -> str:
        value = unquote(
            "/".join(part.strip("/") for part in (host, path) if part.strip("/"))
        ).strip("/")
        if not value or ".." in value.split("/") or "\\" in value:
            raise ProviderError("Tyche source_url must contain a valid route")
        return cls._ROUTE_PREFIX + value if "/" not in value else "/" + value

    @staticmethod
    def _field(query: dict, name: str, default: str) -> str:
        value = query.get(name, [default])[-1].strip()
        if not value or len(value) > 200 or any(ord(char) < 32 for char in value):
            raise ProviderError("Tyche %s must be a valid field name" % name)
        return value

    def _optional_field(
        self, query: dict, name: str, default: Optional[str],
    ) -> Optional[str]:
        if name not in query:
            return default
        value = query[name][-1].strip()
        return self._field(query, name, value) if value else None

    @staticmethod
    def _parameter_value(value: str) -> Any:
        cleaned = value.strip()
        try:
            return json.loads(cleaned)
        except (TypeError, ValueError):
            return cleaned

    def _time_body(
        self, source: Dict[str, Any], now: Optional[datetime],
        temporal_range: Optional[Tuple[str, str]],
    ) -> dict:
        start, end = self._bounds(now, temporal_range)
        if start > end:
            raise ProviderError("Tyche temporal range starts after it ends")
        window = {"gte": self._format(start), "lte": self._format(end)}
        if source["time_from_field"]:
            return {
                source["time_from_field"]: window["gte"],
                source["time_to_field"]: window["lte"],
            }
        return {source["time_field"]: {"match": window}}

    def _bounds(self, now, temporal_range) -> Tuple[datetime, datetime]:
        if temporal_range is not None:
            return tuple(self._parse_time(value) for value in temporal_range)
        end = self._as_utc(now or datetime.now(timezone.utc))
        return end - self._DEFAULT_LOOKBACK, end

    def _parse_time(self, value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except (AttributeError, ValueError) as exc:
            raise ProviderError(
                "Tyche received an invalid temporal bound: %s" % value
            ) from exc
        return self._as_utc(parsed)

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    def _format(self, value: datetime) -> str:
        return self._as_utc(value).astimezone(timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S.%f"
        )[:-3]

    def _parse_geometry(self, value: object) -> Optional[BaseGeometry]:
        if isinstance(value, BaseGeometry):
            return value
        if isinstance(value, dict):
            return self._from_mapping(value)
        if isinstance(value, (list, tuple)):
            return self._point(*value[:2]) if len(value) >= 2 else None
        return self._from_text(value)

    def _from_mapping(self, value: dict) -> Optional[BaseGeometry]:
        if value.get("type") == "Feature":
            return self._parse_geometry(value.get("geometry"))
        if "type" in value and "coordinates" in value:
            try:
                return shape(value)
            except (TypeError, ValueError):
                return None
        for key in ("geometry", "geo", "wkt", "WKT"):
            if key in value:
                return self._parse_geometry(value[key])
        lon = value.get("lon", value.get("lng", value.get("longitude")))
        lat = value.get("lat", value.get("latitude"))
        return self._point(lon, lat)

    def _from_text(self, value: object) -> Optional[BaseGeometry]:
        if not isinstance(value, str) or not value.strip():
            return None
        text = value.strip()
        if text[0] in "[{":
            try:
                return self._parse_geometry(json.loads(text))
            except (TypeError, ValueError, json.JSONDecodeError):
                return None
        try:
            return wkt.loads(text)
        except Exception:
            return None

    @staticmethod
    def _point(lon: object, lat: object) -> Optional[BaseGeometry]:
        if isinstance(lon, (int, float)) and isinstance(lat, (int, float)):
            return Point(lon, lat)
        return None

    @staticmethod
    def _gdf(valid: List[tuple], geometry_field: str) -> gpd.GeoDataFrame:
        if not valid:
            return empty_features_gdf()
        attributes = [
            {key: value for key, value in row.items() if key != geometry_field}
            for row, _ in valid
        ]
        return gpd.GeoDataFrame(
            attributes, geometry=[geometry for _, geometry in valid], crs=WGS84,
        )

    def _declared_field(self, item: tuple, rows: List[dict]) -> LayerField:
        name, field_type, description = item
        return LayerField(
            name=name, type=field_type, description=description,
            samples=self._samples(rows, name),
        )

    def _extra_fields(
        self, declared: List[LayerField], rows: List[dict],
        geometry_field: str, temporal_field: str,
    ) -> List[LayerField]:
        known = {field.name for field in declared}
        names = dict.fromkeys(
            str(key) for row in rows for key in row if key != geometry_field
        )
        return [
            LayerField(
                name=name,
                type="date" if name == temporal_field else "string",
                samples=self._samples(rows, name),
            )
            for name in names if name not in known
        ]

    @staticmethod
    def _samples(rows: List[dict], name: str) -> List[str]:
        values = [
            str(row[name])[:80] for row in rows if row.get(name) is not None
        ]
        return list(dict.fromkeys(values))[:5]
