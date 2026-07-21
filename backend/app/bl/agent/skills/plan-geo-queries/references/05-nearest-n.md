# `nearest_n`

**Use when:** Return the global N subject features closest to any feature in one real reference layer, such as “the 3 schools nearest a park”.

**Do not use when:** The request gives a maximum distance (`near`), requires every one of multiple references (`near_all`), or says “nearest” without naming a sensible reference—clarify instead of inventing one.

**Emit:** `{"id":"s5","op":"nearest_n","input":"s4","target_layer":"id","count":3,"target_field":"optional","target_operator":"eq|contains","target_value":"optional"}`

`count` is a result limit from 1 through 50, not an aggregate. For one named reference entity, emit the full target field/operator/value triple; otherwise omit it. Add the target layer to `context_layers`.
