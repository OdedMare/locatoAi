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
    "trajectory_relation": (
        "relation", "entity_field", "time_field", "max_distance_m",
        "time_tolerance_minutes", "max_gap_minutes", "min_duration_minutes",
        "min_time_separation_minutes", "min_movement_distance_m",
    ),
    "origin_movement": (
        "pattern", "start_at", "end_at", "entity_field", "time_field",
        "time_tolerance_minutes", "min_departure_distance_m",
        "max_return_distance_m",
    ),
    "latest_per_entity": ("entity_field", "time_field"),
    "within_geometry": ("geometry",),
}


class ConstraintPreserver:
    @classmethod
    def preserves(cls, original: GeoQueryPlan, revised: GeoQueryPlan) -> bool:
        revised_signatures = cls._signatures(revised)
        return all(
            signature in revised_signatures for signature in cls._signatures(original)
        )

    @staticmethod
    def _signatures(plan: GeoQueryPlan):
        result = []
        for step in plan.steps:
            fields = _CONSTRAINT_FIELDS.get(step.op)
            if fields:
                data = step.model_dump(by_alias=True)
                result.append((step.op, tuple(json.dumps(data.get(name), sort_keys=True,
                                                         ensure_ascii=False)
                                              for name in fields)))
        return result


preserves_constraints = ConstraintPreserver.preserves
