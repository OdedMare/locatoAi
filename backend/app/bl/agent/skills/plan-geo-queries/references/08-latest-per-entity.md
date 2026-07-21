# `latest_per_entity`

**Use when:** Collapse repeated moving-entity observations to the newest row per stable entity after requested boundary, time, attribute, and spatial filters. Use before returning or counting distinct Tyche/Cubes entities and before clustering them.

**Do not use when:** The request asks whether or where an entity moved; use `movement_direction`, which already returns one latest row per matching entity.

**Emit:** `{"id":"s8","op":"latest_per_entity","input":"s7","entity_field":"netId","time_field":"eventTime"}`

Use only fields present in the moving layer schema. Tyche/Cubes defaults are `netId` and `eventTime`.
