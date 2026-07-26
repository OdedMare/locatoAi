"""Queryable field metadata for a catalog layer."""

from typing import List

from pydantic import BaseModel


class LayerField(BaseModel):
    """A few distinct example values — lets the plan agent write attribute
    filters that match the data's language/format."""

    name: str
    type: str
    description: str = ""
    samples: List[str] = []
    metadata_relevant: bool = True
