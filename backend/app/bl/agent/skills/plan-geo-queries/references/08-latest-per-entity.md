# `latest_per_entity`

**Use when:** Collapse repeated observations to the newest row per stable entity after requested boundary, time, attribute, and spatial filters. Use before returning, counting, or clustering distinct entities.

**Do not use when:** The request asks whether or where an entity moved; use `movement_direction`, which already returns one latest row per matching entity.

Use the layer schema's declared `entity` and `time` roles. If either role is missing, clarify instead of guessing a field.
