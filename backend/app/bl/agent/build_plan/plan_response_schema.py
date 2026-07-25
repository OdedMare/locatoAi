"""JSON Schema for every valid plan-builder response shape."""

from app.bl.plan.models.geo_query_plan import GeoQueryPlan


def _tool(name: str, fields: dict) -> dict:
    properties = {"tool": {"const": name}, **fields}
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _build() -> dict:
    plan = GeoQueryPlan.model_json_schema()
    definitions = plan.pop("$defs", {})
    return {
        "$defs": definitions,
        "anyOf": [
            plan,
            _tool(
                "sample_field",
                {"layer_id": {"type": "string"}, "field": {"type": "string"}},
            ),
            _tool("load_skill", {"skill_id": {"type": "string"}}),
            {
                "type": "object",
                "properties": {"clarify": {"type": "string"}},
                "required": ["clarify"],
                "additionalProperties": False,
            },
        ],
    }


PLAN_RESPONSE_SCHEMA = _build()
