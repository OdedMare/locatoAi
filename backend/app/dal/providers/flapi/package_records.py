"""Convert flunks' DataFrame result into JSON-safe records."""

from typing import Any, List

from app.common.errors.provider_error import ProviderError


class FlowPackageRecords:
    """Normalizes geometry, missing values, and numpy scalars."""

    @classmethod
    def normalize(cls, result: Any) -> List[dict]:
        if not cls.is_dataframe(result):
            raise ProviderError(
                "flunks returned %s; expected a DataFrame"
                % type(result).__name__
            )
        return [cls._record(row) for row in result.to_dict("records")]

    @staticmethod
    def is_dataframe(result: Any) -> bool:
        # Duck-typed so the gateway needs no pandas import to check the type,
        # and so a geopandas GeoDataFrame matches the same branch.
        return hasattr(result, "to_dict") and hasattr(result, "columns")

    @classmethod
    def _record(cls, row: dict) -> dict:
        return {str(key): cls._value(value) for key, value in row.items()}

    @classmethod
    def _value(cls, value: Any) -> Any:
        if value is None:
            return None
        if cls._is_missing(value):
            return None
        wkt_text = getattr(value, "wkt", None)
        if wkt_text is not None and hasattr(value, "geom_type"):
            return wkt_text
        item = getattr(value, "item", None)
        if item is not None and hasattr(value, "dtype"):
            # numpy scalar -> the equivalent Python int/float/bool/str.
            return item()
        return value

    @staticmethod
    def _is_missing(value: Any) -> bool:
        try:
            import pandas as pd
        except ImportError:  # pragma: no cover - pandas ships with geopandas
            return False
        try:
            missing = pd.isna(value)
        except (TypeError, ValueError):
            # pd.isna returns an array for list/array cells; those are present.
            return False
        return missing is True

    @staticmethod
    def row_count(result: Any) -> int:
        """Return the row count without materializing records."""
        try:
            return len(result)
        except TypeError:
            return 0
