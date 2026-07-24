# `movement_direction`

**Use when:** A moving-entity layer has multiple observations per id and the user asks for entities that moved, traveled, or moved north/south/east/west during a requested time window.

**Do not use when:** The user asks for a static northern/southern/eastern/western feature (`directional`) or only the newest observation (`latest_per_entity`). Do not add `latest_per_entity` after this operation.

Apply a requested `temporal_filter` first. Use `any` for movement without a bearing; it measures total path length. Compass directions use dominant first-to-last displacement. Use the layer schema's declared `entity` and `time` roles, and omit an unstated movement threshold so the contract supplies the default.
