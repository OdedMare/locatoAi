from typing import Literal

from pydantic import BaseModel, Field


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
