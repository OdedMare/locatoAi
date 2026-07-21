# `between`

**Use when:** Keep subject features intersecting a buffered corridor joining two reference entities or layers, for “between A and B / בין A ל-B”. The two references may be filtered entities from the same catalog layer.

**Do not use when:** The request only means close to both references (`near_all`) or requires an exact topology predicate (`crosses`, `touches`, `contains`).

**Emit:** `{"id":"s11","op":"between","input":"s10","first_target_layer":"id","second_target_layer":"id","corridor_width_m":100,"first_target_field":"optional","first_target_operator":"eq|contains","first_target_value":"optional","second_target_field":"optional","second_target_operator":"eq|contains","second_target_value":"optional"}`

Use 100 m when no corridor width is stated; valid range is greater than 0 through 5000. For each named endpoint, emit its complete field/operator/value triple. Add both target layers to `context_layers`.
