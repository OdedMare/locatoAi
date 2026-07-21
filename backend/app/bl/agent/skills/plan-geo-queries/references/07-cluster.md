# `cluster`

**Use when:** Find groups of at least N distinct features from the same input layer that are close to one another, such as “3 bases near each other” or “שני אמבולנסים קרובים”.

**Do not use when:** Comparing a subject with another reference layer (`near`, `nearest_n`, or `near_all`). For repeated moving observations, run `latest_per_entity` first so one entity cannot form a group with itself.

**Emit:** `{"id":"s7","op":"cluster","input":"s6","min_group_size":3,"max_distance_m":300}`

Set group size from 2 through 20 and distance greater than 0 through 5000 m; use 300 m for unspecified “near each other”. Results contain `cluster_id` and may include several groups.
