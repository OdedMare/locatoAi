"""Normalize whatever ``FlunksRunner.run()`` returns into plain JSON records.

flunks may hand back a pandas/geopandas DataFrame rather than the ``list[dict]``
the gateway originally assumed. Converting is not just ``to_dict("records")``:
a DataFrame carries three things the rest of the pipeline cannot read.

* **Geometry as shapely objects.** ``FlapiSchemaMapper._point`` only parses a
  ``str``, so a shapely cell is silently dropped and the layer returns zero
  features with no error at all. Geometry is rendered back to WKT here.
* **``NaN`` for missing cells.** ``NaN`` is not ``None``, so it survives every
  ``value is not None`` guard in schema inference — a numeric column with gaps
  gets typed ``"string"`` and ``"nan"`` reaches the agent as a sample value.
* **numpy scalars.** ``numpy.int64`` fails ``isinstance(value, int)`` in field
  typing and is not JSON-serializable downstream.

Pandas is imported lazily: it is already a geopandas dependency, but the list
path must not pay an import for a conversion it never performs.
"""

from typing import Any, List


class FlowPackageRecords:
    """Converts a flunks result into a list of JSON-safe dicts."""

    @classmethod
    def normalize(cls, result: Any) -> Any:
        """Return ``result`` unchanged unless it is a DataFrame."""
        if not cls.is_dataframe(result):
            return result
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
        """Row count without materializing records, for the size guard."""
        try:
            return len(result)
        except TypeError:
            return 0
