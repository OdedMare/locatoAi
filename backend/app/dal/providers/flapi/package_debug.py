"""Render Flow Package execution details for the request log.

Every value FLAPI rejects has been invisible from our side so far: an empty
input cube, a boundary that never arrived, an unexpected record shape. These
helpers turn each of those into one bounded log line — enough to diagnose a
failed package run from the console without dumping whole feature bodies.
"""

from typing import Any, List, Optional

_WKT_PREVIEW_CHARS = 120
_MAX_LOGGED_VALUES = 3
_MAX_LOGGED_KEYS = 25


class FlowPackageDebug:
    """Bounded, log-safe descriptions of package inputs and outputs."""

    @classmethod
    def input_cube(cls, cube: Any) -> str:
        """One line describing what the package is actually being sent."""
        kind = "time" if getattr(cube, "start_time", None) else "values"
        parts = [
            "cube_name=%r" % getattr(cube, "cube_name", None),
            "cube_parameter=%r" % getattr(cube, "cube_parameter", None),
            "input_kind=%s" % kind,
        ]
        if kind == "time":
            parts.append("start_time=%s" % getattr(cube, "start_time", None))
            parts.append("end_time=%s" % getattr(cube, "end_time", None))
        else:
            parts.append(cls._values(getattr(cube, "values", None)))
        return " ".join(parts)

    @classmethod
    def _values(cls, values: Optional[list]) -> str:
        if not values:
            # The failure mode FLAPI reports as "Please enter values for the
            # main cube input" — call it out explicitly rather than "[]".
            return "values=EMPTY (FLAPI will reject this)"
        previews = [cls._preview(value) for value in values[:_MAX_LOGGED_VALUES]]
        extra = len(values) - len(previews)
        return "values=%d%s [%s]" % (
            len(values),
            " (+%d more)" % extra if extra > 0 else "",
            "; ".join(previews),
        )

    @staticmethod
    def _preview(value: Any) -> str:
        text = str(value)
        if len(text) <= _WKT_PREVIEW_CHARS:
            return text
        # Keep the geometry type and opening coordinates — enough to tell a
        # MULTIPOLYGON from a POINT and to eyeball lon/lat order.
        return "%s… (%d chars total)" % (text[:_WKT_PREVIEW_CHARS], len(text))

    @staticmethod
    def geometry(geometry: Any) -> str:
        """Describe the boundary handed to a package, including its absence."""
        if geometry is None:
            return "geometry=None"
        if getattr(geometry, "is_empty", False):
            return "geometry=EMPTY"
        parts = getattr(geometry, "geoms", None)
        return "geometry=%s parts=%d bounds=%s" % (
            getattr(geometry, "geom_type", "?"),
            len(list(parts)) if parts is not None else 1,
            tuple(round(value, 5) for value in geometry.bounds),
        )

    @staticmethod
    def records(records: List[dict]) -> str:
        """Summarize returned rows by count and observed keys."""
        if not records:
            return "records=0"
        keys: List[str] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            for key in record:
                if key not in keys and len(keys) < _MAX_LOGGED_KEYS:
                    keys.append(key)
        return "records=%d keys=%s" % (len(records), keys)
