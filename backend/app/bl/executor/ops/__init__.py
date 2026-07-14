"""Importing this package registers every op handler."""

from app.bl.executor.ops import (  # noqa: F401
    attribute_filter,
    count,
    directional,
    load,
    near,
    nearest_n,
    temporal_filter,
    within_geometry,
)
