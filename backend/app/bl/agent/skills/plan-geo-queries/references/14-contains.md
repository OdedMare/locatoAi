# `contains`

**Use when:** Keep input geometries that fully contain a reference geometry.

**Do not use when:** The requested direction is reversed (“features inside X” is not expressible by this input-contains-target operation), the geometries only cross or touch, or the user merely asks for proximity.

**Emit:** `{"id":"s14","op":"contains","input":"s13","target_layer":"id","target_field":"optional","target_operator":"eq|contains","target_value":"optional"}`

Direction is strict: INPUT contains TARGET. For a named target, emit the complete target filter triple; otherwise omit it. Add the target layer to `context_layers`.
