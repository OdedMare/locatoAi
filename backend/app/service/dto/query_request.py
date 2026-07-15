from pydantic import BaseModel, Field

from app.service.dto.geo_json_multi_polygon import GeoJSONMultiPolygon


class QueryRequest(BaseModel):
    """The contract with the frontend: exactly {query, boundaries}."""

    query: str = Field(min_length=1)
    boundaries: GeoJSONMultiPolygon
