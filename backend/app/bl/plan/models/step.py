from typing import Union

from pydantic import Field
from typing_extensions import Annotated

from app.bl.plan.models.attribute_filter_step import AttributeFilterStep
from app.bl.plan.models.between_step import BetweenStep
from app.bl.plan.models.cluster_step import ClusterStep
from app.bl.plan.models.contains_step import ContainsStep
from app.bl.plan.models.count_step import CountStep
from app.bl.plan.models.crosses_step import CrossesStep
from app.bl.plan.models.directional_step import DirectionalStep
from app.bl.plan.models.latest_per_entity_step import LatestPerEntityStep
from app.bl.plan.models.load_step import LoadStep
from app.bl.plan.models.movement_direction_step import MovementDirectionStep
from app.bl.plan.models.near_all_step import NearAllStep
from app.bl.plan.models.near_step import NearStep
from app.bl.plan.models.nearest_n_step import NearestNStep
from app.bl.plan.models.round_trip_step import RoundTripStep
from app.bl.plan.models.temporal_filter_step import TemporalFilterStep
from app.bl.plan.models.touches_step import TouchesStep
from app.bl.plan.models.trajectory_relation_step import TrajectoryRelationStep
from app.bl.plan.models.within_geometry_step import WithinGeometryStep

Step = Annotated[
    Union[
        LoadStep,
        WithinGeometryStep,
        AttributeFilterStep,
        NearStep,
        NearestNStep,
        NearAllStep,
        BetweenStep,
        CrossesStep,
        TouchesStep,
        ContainsStep,
        DirectionalStep,
        TemporalFilterStep,
        ClusterStep,
        LatestPerEntityStep,
        MovementDirectionStep,
        TrajectoryRelationStep,
        RoundTripStep,
        CountStep,
    ],
    Field(discriminator="op"),
]
