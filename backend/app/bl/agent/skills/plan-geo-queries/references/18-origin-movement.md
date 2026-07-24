# `origin_movement`

**Use when:** Find entities that left their starting place during a requested time window, or left and returned near it. This supports departures during an explicit night window.

**Do not use when:** The user only asks whether an entity moved (`movement_direction`) or compares different entities (`trajectory_relation`). A track's first observation is only an inferred origin, not proof of a home address; if verified home semantics matter, clarify. Do not guess a missing date, AM/PM, timezone, or definition of “night.”

**Emit:** `{"id":"s18","op":"origin_movement","input":"s17","pattern":"departed|round_trip","start_at":"ISO-8601","end_at":"ISO-8601","entity_field":"schema identity field","time_field":"schema time field","time_tolerance_minutes":15,"min_departure_distance_m":100,"max_return_distance_m":100}`

Apply `temporal_filter` from `start_at` through `end_at` first. Choose stable identity/time fields from the schema. `departed` requires a start observation within the time tolerance and later movement at least `min_departure_distance_m` away; it treats that first matched point as an inferred origin. `round_trip` additionally requires an end observation within the tolerance, at least one intermediate observation, and a finish within `max_return_distance_m` of the origin. Results state how the origin was inferred and include the complete path and distance metrics.
