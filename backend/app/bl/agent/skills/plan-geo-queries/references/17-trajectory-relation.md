# `trajectory_relation`

**Use when:** Compare repeated observations of different moving entities: moving or staying together, reaching the same destination, moving at the same time, or visiting the same place at different times.

**Do not use when:** The query concerns one entity's direction (`movement_direction`), one entity leaving its origin or returning to it (`origin_movement`), only the newest observation (`latest_per_entity`), or a static same-layer group (`cluster`). Do not collapse observations before this operation.

Apply the requested `temporal_filter` first and use the schema's declared `entity` and `time` roles. `together` aligns observations in space and time; use a zero movement threshold only for staying together. `same_destination` compares final positions and arrival times. `same_time` compares movement intervals without requiring the same location. `same_place_different_times` compares visits separated in time.
