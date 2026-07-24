# `nearest_n`

**Use when:** Return the global N subject features closest to any feature in one selected reference layer.

**Do not use when:** The request gives a maximum distance (`near`), requires every one of multiple references (`near_all`), or says “nearest” without naming a sensible reference—clarify instead of inventing one.

Use the latest subject-chain step as input. `count` is the user's result limit, not an aggregate. A named reference entity requires the complete target filter. Add the reference layer to `context_layers`.
