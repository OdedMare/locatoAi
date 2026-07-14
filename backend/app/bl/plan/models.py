"""The Geo Query Plan — the core contract of the system.

Locked decisions:
- The agent emits a plan, never SQL.
- The plan is a DAG of steps chained by `id` / `input` references.
- Steps are a Pydantic discriminated union on `op`; unknown ops are
  rejected at parse time.

`layer` / `target_layer` reference catalog layer ids (UUIDs from
public.layers).
"""

from typing import List, Literal, Union

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


class NearestNStep(BaseModel):
    id: str
    op: Literal["nearest_n"]
    input: str
    target_layer: str
    count: int = Field(gt=0, le=50)


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
        DirectionalStep,
        TemporalFilterStep,
        CountStep,
    ],
    Field(discriminator="op"),
]


class GeoQueryPlan(BaseModel):
    explanation: str
    steps: List[Step]
    output: str
    context_layers: List[str] = []
