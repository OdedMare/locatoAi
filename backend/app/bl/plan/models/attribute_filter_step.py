from typing import Literal, Union

from pydantic import BaseModel


class AttributeFilterStep(BaseModel):
    id: str
    op: Literal["attribute_filter"]
    input: str
    field: str
    operator: Literal["eq", "neq", "gt", "lt", "contains"]
    value: Union[str, float]
