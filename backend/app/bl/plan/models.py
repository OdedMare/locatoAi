"""The Geo Query Plan — the core contract of the system.

Locked decisions:
- The agent emits a plan, never SQL.
- The plan is a DAG of steps chained by `id` / `input` references.
- Steps are a Pydantic discriminated union on `op`; unknown ops are
  rejected at parse time.

`layer` / `target_layer` reference catalog layer ids (UUIDs from
public.layers).
"""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


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
    value: str | float


class NearStep(BaseModel):
    id: str
    op: Literal["near"]
    input: str
    target_layer: str
    distance_m: float = Field(gt=0, le=5000)


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


Step = Annotated[
    Union[
        LoadStep,
        WithinGeometryStep,
        AttributeFilterStep,
        NearStep,
        DirectionalStep,
        TemporalFilterStep,
    ],
    Field(discriminator="op"),
]


class GeoQueryPlan(BaseModel):
    explanation: str
    steps: list[Step]
    output: str
    context_layers: list[str] = []
