# `near_all`

**Use when:** Every subject feature must be near every one of 2–5 simultaneous references (AND semantics), including “2 soldiers near the square and the school”, Hebrew `ו`, or “near A where B is”. Optionally rank by mean reference distance and keep N results.

**Do not use when:** Only one reference exists (`near`/`nearest_n`) or features must be near each other within the same subject layer (`cluster`). Never chain `nearest_n` for multi-reference proximity.

**Emit:** `{"id":"s6","op":"near_all","input":"s5","targets":[{"layer":"id","field":"optional","operator":"eq|contains","value":"optional"},{"layer":"id"}],"distance_m":300,"count":2}`

Use 300 m when no distance is stated; valid range is greater than 0 through 5000. `count` is optional and limited to 1–50. Each named target needs its complete field/operator/value triple; omit all three for a whole layer. Add every target layer to `context_layers`.
