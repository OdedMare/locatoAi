"""JSON Schema for every valid plan-builder response shape."""

from app.bl.plan.models.geo_query_plan import GeoQueryPlan


class PlanResponseSchema:
    @classmethod
    def build(cls) -> dict:
        return {
            "anyOf": [
                GeoQueryPlan.model_json_schema(),
                cls._tool(
                    "sample_field",
                    {"layer_id": {"type": "string"}, "field": {"type": "string"}},
                ),
                cls._tool(
                    "load_skill", {"skill_id": {"type": "string"}},
                ),
                {
                    "type": "object",
                    "properties": {"clarify": {"type": "string"}},
                    "required": ["clarify"],
                    "additionalProperties": False,
                },
            ]
        }

    @staticmethod
    def _tool(name: str, fields: dict) -> dict:
        properties = {"tool": {"const": name}, **fields}
        return {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        }


PLAN_RESPONSE_SCHEMA = PlanResponseSchema.build()
