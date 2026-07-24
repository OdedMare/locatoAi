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
    origin_movement,
    temporal_filter,
    trajectory_relation,
    within_geometry,
)
from app.bl.executor.ops.spatial_relation import (  # noqa: F401
    contains_op,
    crosses_op,
    touches_op,
)
