import json

from app.bl.plan.models.geo_query_plan import GeoQueryPlan

_CONSTRAINT_FIELDS = {
    "attribute_filter": ("field", "operator", "value"),
    "near": ("target_layer", "distance_m", "target_field", "target_operator", "target_value"),
    "nearest_n": ("target_layer", "count", "target_field", "target_operator", "target_value"),
    "near_all": ("targets", "distance_m", "count"),
    "between": ("first_target_layer", "second_target_layer", "corridor_width_m"),
    "temporal_filter": ("from", "to"),
    "cluster": ("min_group_size", "max_distance_m"),
    "movement_direction": ("direction", "entity_field", "time_field", "min_distance_m"),
    "latest_per_entity": ("entity_field", "time_field"),
    "within_geometry": ("geometry",),
}


def preserves_constraints(original: GeoQueryPlan, revised: GeoQueryPlan) -> bool:
    def signatures(plan: GeoQueryPlan):
        result = []
        for step in plan.steps:
            fields = _CONSTRAINT_FIELDS.get(step.op)
            if fields:
                data = step.model_dump(by_alias=True)
                result.append((step.op, tuple(json.dumps(data.get(name), sort_keys=True,
                                                         ensure_ascii=False)
                                              for name in fields)))
        return result
    revised_signatures = signatures(revised)
    return all(signature in revised_signatures for signature in signatures(original))
