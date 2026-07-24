# `origin_movement`

**Use when:** Find entities that left their starting place during a requested time window, or left and returned near it. This supports departures during an explicit night window.

**Do not use when:** The user only asks whether an entity moved (`movement_direction`) or compares different entities (`trajectory_relation`). A track's first observation is only an inferred origin, not proof of a home address; if verified home semantics matter, clarify. Do not guess a missing date, AM/PM, timezone, or definition of “night.”

Apply `temporal_filter` over the same interval first and use the schema's declared `entity` and `time` roles. `departed` requires later movement away from the inferred origin. `round_trip` additionally requires an intermediate observation and a finish near that origin.
