from typing import List

from pydantic import BaseModel


class LayerMeta(BaseModel):
    """One row of the catalog (public.layers). Metadata only — never features."""

    id: str
    name: str
    description: str = ""
    tags: List[str] = []
    provider: str
    source_url: str
