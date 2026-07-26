# `cluster`

**Use when:** Find groups of at least N distinct features from the same input layer that are close to one another.

**Do not use when:** Comparing a subject with another reference layer (`near`, `nearest_n`, or `near_all`). For repeated moving observations, run `latest_per_entity` first so one entity cannot form a group with itself.

**Compose:** Set `min_group_size` from the request. Set a requested distance; otherwise omit it so the contract supplies the default. Results contain `cluster_id` and may include several groups.
