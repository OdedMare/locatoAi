# `trajectory_relation`

**Use when:** Compare repeated observations of different moving entities: moving or staying together, reaching the same destination, moving at the same time, or visiting the same place at different times.

**Do not use when:** The query concerns one entity's direction (`movement_direction`), one entity leaving its origin or returning to it (`origin_movement`), only the newest observation (`latest_per_entity`), or a static same-layer group (`cluster`). Do not collapse observations before this operation.

**Emit:** `{"id":"s17","op":"trajectory_relation","input":"s16","relation":"together|same_destination|same_time|same_place_different_times","entity_field":"schema identity field","time_field":"schema time field","max_distance_m":100,"time_tolerance_minutes":5,"max_gap_minutes":15,"min_duration_minutes":0,"min_time_separation_minutes":15,"min_movement_distance_m":50}`

Apply an explicit `temporal_filter` first. Choose the stable identity and observation-time fields from the selected layer schema; they are not always `netId` and `eventTime`. Use `sample_field` or clarify if a stable identity field cannot be determined. `together` aligns observations using both the spatial and time buffers; use `min_movement_distance_m=0` for “stayed together” and a positive threshold for “moved/traveled together.” `same_destination` compares final positions and arrival times. `same_time` compares movement intervals and uses `time_tolerance_minutes` as the allowed timing buffer without requiring the same location. `same_place_different_times` finds spatially close observations separated by at least `min_time_separation_minutes`. Results identify related entity IDs and preserve each matching path.
