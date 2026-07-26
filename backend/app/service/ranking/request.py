from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.service.shared.geo_json_multi_polygon import GeoJSONMultiPolygon


class RankingRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    boundaries: GeoJSONMultiPolygon
    subject_layer_id: str = Field(min_length=1)
    from_: Optional[datetime] = Field(default=None, alias="from")
    to: Optional[datetime] = None
    limit: int = Field(default=200, ge=1, le=5000)

    @model_validator(mode="after")
    def validate_window(self):
        for value in (self.from_, self.to):
            if value is not None and value.utcoffset() is None:
                raise ValueError("Ranking times must include a timezone")
        if self.from_ is not None and self.to is not None:
            if self.from_ > self.to:
                raise ValueError("'from' must not exceed 'to'")
        return self
