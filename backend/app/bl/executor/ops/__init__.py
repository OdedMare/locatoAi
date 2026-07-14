"""Importing this package registers every op handler."""

from app.bl.executor.ops import (  # noqa: F401
    attribute_filter,
    between,
    count,
    directional,
    load,
    near,
    nearest_n,
    spatial_relation,
    temporal_filter,
    within_geometry,
)
