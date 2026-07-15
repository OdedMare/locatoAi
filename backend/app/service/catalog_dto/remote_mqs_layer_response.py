from typing import List

from pydantic import BaseModel


class RemoteMqsLayerResponse(BaseModel):
    id: str
    name: str
    description: str
    tags: List[str]
    provider: str
    source_url: str
