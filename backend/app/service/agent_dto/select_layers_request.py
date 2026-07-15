from pydantic import BaseModel, Field


class SelectLayersRequest(BaseModel):
    query: str = Field(min_length=1)
