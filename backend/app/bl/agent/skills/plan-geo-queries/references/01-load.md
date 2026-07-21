# `load`

**Use when:** Start every subject/output chain by loading one selected catalog layer.

**Do not use when:** A layer is only a spatial reference for `near`, `nearest_n`, `near_all`, `between`, `crosses`, `touches`, or `contains`; those operations load references internally.

**Emit:** `{"id":"s1","op":"load","layer":"id"}`

Use only a layer id supplied in `LAYERS`. A plain “show X” request may end after this step when no other constraint is requested.
