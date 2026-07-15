from pydantic import BaseModel

from app.bl.plan.models.geo_query_plan import GeoQueryPlan
from app.service.dto.geo_json_multi_polygon import GeoJSONMultiPolygon


class ExecutePlanRequest(BaseModel):
    """Debug endpoint input: a hand-written plan (no AI involved)."""

    plan: GeoQueryPlan
    boundaries: GeoJSONMultiPolygon
