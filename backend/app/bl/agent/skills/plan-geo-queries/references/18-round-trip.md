# `round_trip`

**Use when:** Find entities observed near their starting place at a requested departure time, which traveled away and returned near that place at a requested return time.

**Do not use when:** The user only asks whether an entity moved (`movement_direction`) or compares different entities (`trajectory_relation`). Do not guess a missing date, AM/PM, or timezone for bare clock times; clarify first.

**Emit:** `{"id":"s18","op":"round_trip","input":"s17","depart_at":"ISO-8601","return_at":"ISO-8601","entity_field":"schema identity field","time_field":"schema time field","time_tolerance_minutes":15,"min_departure_distance_m":100,"max_return_distance_m":100}`

Apply `temporal_filter` from `depart_at` through `return_at` first. Choose the stable identity and observation-time fields from the selected layer schema; do not assume one provider's field names. The time tolerance requires an observation close to each endpoint; the entity must have at least one intermediate observation, travel at least `min_departure_distance_m` away from its starting point, and finish within `max_return_distance_m` of it. Results use the matched return observation and include the complete round-trip path and distance metrics.
