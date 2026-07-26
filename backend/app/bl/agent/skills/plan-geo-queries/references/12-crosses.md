# `crosses`

**Use when:** Keep input geometries whose interiors cross a reference geometry while neither contains the other. This is most useful for a line crossing another line or polygon.

**Do not use when:** The relationship is only proximity (`near`), boundary contact without interior overlap (`touches`), containment (`contains`), or a broad corridor between two references (`between`).

**Compose:** Use the latest subject-chain step as input. A named reference requires its complete target filter. Add the reference layer to `context_layers`.
