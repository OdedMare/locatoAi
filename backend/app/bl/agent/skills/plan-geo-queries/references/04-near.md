# `near`

**Use when:** Keep subject features within a distance threshold of any feature in exactly one different reference layer, such as “schools within 500 m of parks” or “חייל ליד בית ספר”.

**Do not use when:** The user asks for the N closest (`nearest_n`), simultaneous proximity to several references (`near_all`), or close features within the subject layer itself (`cluster`).

**Emit:** `{"id":"s4","op":"near","input":"s3","target_layer":"id","distance_m":300,"target_field":"optional","target_operator":"eq|contains","target_value":"optional"}`

Set `distance_m` to the requested value; use 300 when “near/ליד” has no number. Valid range is greater than 0 through 5000. For one named reference entity, emit all three `target_*` fields; for the whole reference layer, omit all three. Add the target layer to `context_layers`.
