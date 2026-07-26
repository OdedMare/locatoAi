from typing import Literal

from pydantic import BaseModel


class CountStep(BaseModel):
    """Terminal aggregation: row count of the upstream step, as a plain
    int. No grouping/aggregation by attribute. Must be the plan's `output`
    and the last step — enforced in validators.py, not here, since that
    check needs whole-plan context."""

    id: str
    op: Literal["count"]
    input: str
