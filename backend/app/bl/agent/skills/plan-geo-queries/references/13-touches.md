# `touches`

**Use when:** Keep input geometries whose boundaries contact a reference geometry without their interiors overlapping.

**Do not use when:** The interiors cross (`crosses`), the input fully contains the reference (`contains`), or the user merely says near/adjacent without exact boundary semantics (`near`).

Use the latest subject-chain step as input. A named reference requires its complete target filter. Add the reference layer to `context_layers`.
