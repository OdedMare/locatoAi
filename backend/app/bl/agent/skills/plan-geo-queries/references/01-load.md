# `load`

**Use when:** Start every subject/output chain by loading one selected catalog layer.

**Do not use when:** A layer is only a spatial reference for `near`, `nearest_n`, `near_all`, `between`, `crosses`, `touches`, or `contains`; those operations load references internally.

**Compose:** Use only a subject layer id supplied in `LAYERS`. A plain request to show a layer may end after this step.
