# `near`

**Use when:** Keep subject features within a distance threshold of any feature in exactly one different reference layer.

**Do not use when:** The user asks for the N closest (`nearest_n`), simultaneous proximity to several references (`near_all`), or close features within the subject layer itself (`cluster`).

Use the latest subject-chain step as input and a selected reference layer as the target. Set a user-requested distance; otherwise omit it so the operation contract supplies the default. A named reference entity requires the complete target filter. Add the reference layer to `context_layers`.
