"""The Geo Query Plan — the core contract of the system.

Locked decisions:
- The agent emits a plan, never SQL.
- The plan is a DAG of steps chained by `id` / `input` references.
- Steps are a Pydantic discriminated union on `op`; unknown ops are
  rejected at parse time.

`layer` / `target_layer` reference catalog layer ids (UUIDs from
public.layers).
"""

from typing import List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import Annotated


class LoadStep(BaseModel):
    id: str
    op: Literal["load"]
    layer: str


class WithinGeometryStep(BaseModel):
    id: str
    op: Literal["within_geometry"]
    input: str
    geometry: Literal["user_polygon"] = "user_polygon"


class AttributeFilterStep(BaseModel):
    id: str
    op: Literal["attribute_filter"]
    input: str
    field: str
    operator: Literal["eq", "neq", "gt", "lt", "contains"]
    value: Union[str, float]


class NearStep(BaseModel):
    id: str
    op: Literal["near"]
    input: str
    target_layer: str
    distance_m: float = Field(gt=0, le=5000)
    # A named landmark (for example "Venice Beach") narrows the reference
    # layer before distance calculation. All three fields are emitted together.
    target_field: Optional[str] = None
    target_operator: Optional[Literal["eq", "contains"]] = None
    target_value: Optional[Union[str, float]] = None


class NearestNStep(BaseModel):
    id: str
    op: Literal["nearest_n"]
    input: str
    target_layer: str
    count: int = Field(gt=0, le=50)
    target_field: Optional[str] = None
    target_operator: Optional[Literal["eq", "contains"]] = None
    target_value: Optional[Union[str, float]] = None


class SpatialRelationStep(BaseModel):
    """Base fields shared by topological relations against another layer."""

    id: str
    input: str
    target_layer: str
    target_field: Optional[str] = None
    target_operator: Optional[Literal["eq", "contains"]] = None
    target_value: Optional[Union[str, float]] = None


class CrossesStep(SpatialRelationStep):
    op: Literal["crosses"]


class TouchesStep(SpatialRelationStep):
    op: Literal["touches"]


class ContainsStep(SpatialRelationStep):
    op: Literal["contains"]


class BetweenStep(BaseModel):
    id: str
    op: Literal["between"]
    input: str
    first_target_layer: str
    second_target_layer: str
    corridor_width_m: float = Field(default=100, gt=0, le=5000)
    first_target_field: Optional[str] = None
    first_target_operator: Optional[Literal["eq", "contains"]] = None
    first_target_value: Optional[Union[str, float]] = None
    second_target_field: Optional[str] = None
    second_target_operator: Optional[Literal["eq", "contains"]] = None
    second_target_value: Optional[Union[str, float]] = None


class DirectionalStep(BaseModel):
    id: str
    op: Literal["directional"]
    input: str
    direction: Literal["north", "south", "east", "west"]
    count: int = Field(default=1, ge=1)


class TemporalFilterStep(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    op: Literal["temporal_filter"]
    input: str
    from_: str = Field(alias="from")  # ISO 8601
    to: str  # ISO 8601


class ClusterStep(BaseModel):
    """Find groups of >= min_group_size input features all mutually within
    max_distance_m of each other (a self-join within one layer — distinct
    from near/nearest_n/between, which compare two layers). Output is the
    subset of input features belonging to any qualifying group, each
    tagged with a cluster_id so the UI can distinguish groups; features
    in no qualifying group are dropped."""

    id: str
    op: Literal["cluster"]
    input: str
    min_group_size: int = Field(ge=2, le=20)
    max_distance_m: float = Field(gt=0, le=5000)


class CountStep(BaseModel):
    """Terminal aggregation: row count of the upstream step, as a plain
    int. No grouping/aggregation by attribute. Must be the plan's `output`
    and the last step — enforced in validators.py, not here, since that
    check needs whole-plan context."""

    id: str
    op: Literal["count"]
    input: str


Step = Annotated[
    Union[
        LoadStep,
        WithinGeometryStep,
        AttributeFilterStep,
        NearStep,
        NearestNStep,
        BetweenStep,
        CrossesStep,
        TouchesStep,
        ContainsStep,
        DirectionalStep,
        TemporalFilterStep,
        ClusterStep,
        CountStep,
    ],
    Field(discriminator="op"),
]


class GeoQueryPlan(BaseModel):
    explanation: str
    steps: List[Step]
    output: str
    context_layers: List[str] = []
