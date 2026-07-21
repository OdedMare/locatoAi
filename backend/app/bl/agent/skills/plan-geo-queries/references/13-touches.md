# `touches`

**Use when:** Keep input geometries whose boundaries contact a reference geometry without their interiors overlapping.

**Do not use when:** The interiors cross (`crosses`), the input fully contains the reference (`contains`), or the user merely says near/adjacent without exact boundary semantics (`near`).

**Emit:** `{"id":"s13","op":"touches","input":"s12","target_layer":"id","target_field":"optional","target_operator":"eq|contains","target_value":"optional"}`

For a named reference, emit the complete target filter triple; otherwise omit it. Add the target layer to `context_layers`.
