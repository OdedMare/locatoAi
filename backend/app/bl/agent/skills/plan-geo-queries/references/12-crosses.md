# `crosses`

**Use when:** Keep input geometries whose interiors cross a reference geometry while neither contains the other. This is most useful for a line crossing another line or polygon.

**Do not use when:** The relationship is only proximity (`near`), boundary contact without interior overlap (`touches`), containment (`contains`), or a broad corridor between two references (`between`).

**Emit:** `{"id":"s12","op":"crosses","input":"s11","target_layer":"id","target_field":"optional","target_operator":"eq|contains","target_value":"optional"}`

For a named reference, emit all three target filter fields; otherwise omit them. Add the target layer to `context_layers`.
