# `movement_direction`

**Use when:** A moving-entity layer has multiple observations per id and the user asks for entities that moved, traveled, or moved north/south/east/west during a requested time window.

**Do not use when:** The user asks for a static northern/southern/eastern/western feature (`directional`) or only the newest observation (`latest_per_entity`). Do not add `latest_per_entity` after this operation.

**Emit:** `{"id":"s9","op":"movement_direction","input":"s8","direction":"any|north|south|east|west","entity_field":"netId","time_field":"eventTime","min_distance_m":50}`

Apply `temporal_filter` first. Use `any` for “moved/זז” without a bearing; it measures total path length, including travel that returns near the start. Compass directions use dominant first-to-last displacement, so “north to south/מצפון לדרום” means `south`. Use schema-backed identity/time fields; `min_distance_m` is 0–50000 and defaults to 50.
