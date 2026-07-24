# `between`

**Use when:** Keep subject features intersecting a buffered corridor joining two reference entities or layers. The references may be filtered entities from the same catalog layer.

**Do not use when:** The request only means close to both references (`near_all`) or requires an exact topology predicate (`crosses`, `touches`, `contains`).

Use the latest subject-chain step as input. Set a requested corridor width; otherwise omit it so the contract supplies the default. Each named endpoint requires its complete filter. Add both target layers to `context_layers`.
