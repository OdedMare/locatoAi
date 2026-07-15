"""Importing this package registers every op handler."""

from app.bl.executor.ops import (  # noqa: F401
    attribute_filter,
    between,
    cluster,
    count,
    directional,
    load,
    latest_per_entity,
    movement_direction,
    near,
    near_all,
    nearest_n,
    spatial_relation,
    temporal_filter,
    within_geometry,
)
