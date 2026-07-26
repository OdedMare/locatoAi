"""Translate catalog/query values to and from flunks models."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlsplit

import geopandas as gpd
import pandas as pd
from flunks.config import FlunksPackageConfig
from flunks.flow_models import PackageInputCube, PackageOutputCube
from shapely import wkt
from shapely.geometry import MultiPolygon
from shapely.geometry.base import BaseGeometry

from app.bl.catalog.models.layer_field import LayerField
from app.bl.catalog.models.layer_meta import LayerMeta
from app.bl.catalog.models.layer_schema import LayerSchema
from app.common.errors.provider_error import ProviderError
from app.common.utils.geo_utils import WGS84, empty_features_gdf


class FlunksMapper:
    """Build flunks input and map its DataFrame output."""

    _SAMPLE_WINDOW = timedelta(hours=1)
    _TIME_FIELDS = ("eventTime", "arriveTime", "timestamp", "time", "datetime")

    def package_config(
        self, layer: LayerMeta, geometry: Optional[BaseGeometry] = None,
        temporal_range: Optional[Tuple[str, str]] = None,
        now: Optional[datetime] = None,
    ) -> FlunksPackageConfig:
        options = self._options(layer)
        name = self._required(options, "input_cube_name")
        parameter = self._required(options, "input_cube_parameter")
        output = self._required(options, "output_cube_name")
        cube = self.build_input_cube(
            name, parameter, kind=options.get("input_cube_kind") or "time",
            geometry=geometry, temporal_range=temporal_range, now=now,
        )
        return FlunksPackageConfig(
            package_id=self._package_id(layer), package_name="",
            main_input_cube=cube, output_cube=PackageOutputCube(cube_name=output),
        )

    def build_input_cube(
        self, name: Optional[str], parameter: Optional[str],
        kind: str = "time", geometry: Optional[BaseGeometry] = None,
        temporal_range: Optional[Tuple[str, str]] = None,
        now: Optional[datetime] = None,
    ) -> PackageInputCube:
        if not name:
            raise ProviderError("Flow Package input cube name is required")
        if not parameter:
            raise ProviderError("Flow Package input cube parameter is required")
        return self._input_cube(
            kind, name, parameter, geometry, temporal_range, now,
        )

    def output(
        self, layer: LayerMeta, result: Any, package_id: str, output_name: str,
    ) -> Tuple[gpd.GeoDataFrame, LayerSchema, int]:
        rows = [
            dict(row, _package_query=output_name)
            for row in self.normalize(result)
        ]
        schema = self._schema(layer, rows, package_id)
        return self._gdf(rows), schema, len(rows)

    def normalize(self, result: Any) -> List[dict]:
        if not hasattr(result, "to_dict") or not hasattr(result, "columns"):
            raise ProviderError(
                "flunks returned %s; expected a DataFrame"
                % type(result).__name__
            )
        return [self._record(row) for row in result.to_dict("records")]

    @staticmethod
    def _options(layer: LayerMeta) -> Dict[str, str]:
        query = parse_qs(urlsplit(layer.source_url).query)
        return {
            key: values[0].strip()
            for key, values in query.items() if values and values[0].strip()
        }

    @staticmethod
    def _required(options: Dict[str, str], key: str) -> str:
        value = options.get(key)
        if value:
            return value
        label = key.replace("_", " ")
        raise ProviderError("Flow Package %s is required" % label)

    @staticmethod
    def _package_id(layer: LayerMeta) -> str:
        parsed = urlsplit(layer.source_url.strip())
        parts = [
            part for part in parsed.path.split("/")
            if part and part.casefold() not in {"id", "package"}
        ]
        if not parts:
            raise ProviderError(
                "Flow Package source must be flapi://package/<packageId>"
            )
        return parts[-1]

    def _input_cube(
        self, kind, name, parameter, geometry, temporal_range, now,
    ) -> PackageInputCube:
        if (kind or "").lower() == "geo":
            return PackageInputCube(
                cube_name=name, cube_parameter=parameter,
                values=self._multipolygon(geometry),
            )
        start, end = self._range(temporal_range, now)
        return PackageInputCube(
            cube_name=name, cube_parameter=parameter,
            start_time=start, end_time=end,
        )

    @staticmethod
    def _multipolygon(geometry: Optional[BaseGeometry]) -> List[str]:
        if geometry is None or geometry.is_empty:
            raise ProviderError(
                "Flow Package geographic input requires a query boundary"
            )
        parts = getattr(geometry, "geoms", None)
        polygons = list(parts) if parts is not None else [geometry]
        return [MultiPolygon(polygons).wkt]

    def _range(self, temporal_range, now) -> Tuple[datetime, datetime]:
        if temporal_range is not None:
            return (
                self._parse_time(temporal_range[0]),
                self._parse_time(temporal_range[1]),
            )
        end = now or datetime.now(timezone.utc)
        return end - self._SAMPLE_WINDOW, end

    @staticmethod
    def _parse_time(value: str) -> datetime:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ProviderError(
                "Flow Package temporal range must be ISO 8601"
            ) from exc

    def _record(self, row: dict) -> dict:
        return {str(key): self._value(value) for key, value in row.items()}

    @staticmethod
    def _value(value: Any) -> Any:
        if value is None or (
            pd.api.types.is_scalar(value) and bool(pd.isna(value))
        ):
            return None
        if hasattr(value, "geom_type") and hasattr(value, "wkt"):
            return value.wkt
        if hasattr(value, "dtype") and hasattr(value, "item"):
            return value.item()
        return value

    def _schema(
        self, layer: LayerMeta, rows: List[dict], package_id: str,
    ) -> LayerSchema:
        fields = [self._field(name, rows) for name in self._field_names(rows)]
        names = {field.name for field in fields}
        temporal = next(
            (name for name in self._TIME_FIELDS if name in names), None
        )
        temporal = temporal or next(
            (field.name for field in fields if field.type == "date"), None
        )
        return LayerSchema(
            layer_id=layer.id, source_name="Flow Package %s" % package_id,
            geometry_type="Point", fields=fields, temporal_field=temporal,
            entity_field=layer.entity_field, display_field=layer.display_field,
        )

    def _field(self, name: str, rows: List[dict]) -> LayerField:
        values = [row.get(name) for row in rows]
        return LayerField(
            name=name, type=self._field_type(name, values),
            samples=self._samples(values),
        )

    @staticmethod
    def _field_names(rows: List[dict]) -> List[str]:
        names: List[str] = []
        for row in rows:
            for raw_name in row:
                name = str(raw_name)
                if name != "geometry" and name not in names:
                    names.append(name)
        return names

    def _field_type(self, name: str, values: List[object]) -> str:
        present = [value for value in values if value is not None]
        if name in self._TIME_FIELDS or any(
            self._is_datetime(value) for value in present
        ):
            return "date"
        if present and all(isinstance(value, bool) for value in present):
            return "boolean"
        numeric = all(
            isinstance(value, (int, float)) and not isinstance(value, bool)
            for value in present
        )
        return "number" if present and numeric else "string"

    @staticmethod
    def _is_datetime(value: object) -> bool:
        if not isinstance(value, str) or "T" not in value:
            return False
        try:
            datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            return True
        except ValueError:
            return False

    @staticmethod
    def _samples(values: List[object]) -> List[str]:
        present = [str(value)[:80] for value in values if value is not None]
        return list(dict.fromkeys(present))[:5]

    def _gdf(self, rows: List[dict]) -> gpd.GeoDataFrame:
        parsed = [(row, self._point(row.get("geometry"))) for row in rows]
        valid = [(row, geometry) for row, geometry in parsed if geometry]
        if not valid:
            return empty_features_gdf()
        attributes = [
            {key: value for key, value in row.items() if key != "geometry"}
            for row, _ in valid
        ]
        return gpd.GeoDataFrame(
            attributes, geometry=[geometry for _, geometry in valid], crs=WGS84,
        )

    @staticmethod
    def _point(raw: Any):
        if not isinstance(raw, str):
            return None
        try:
            geometry = wkt.loads(raw)
            return geometry if geometry.geom_type == "Point" else None
        except Exception:
            return None
