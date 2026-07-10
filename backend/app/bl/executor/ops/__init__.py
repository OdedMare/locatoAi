"""Importing this package registers every op handler."""

from app.bl.executor.ops import (  # noqa: F401
    attribute_filter,
    directional,
    load,
    near,
    temporal_filter,
    within_geometry,
)
