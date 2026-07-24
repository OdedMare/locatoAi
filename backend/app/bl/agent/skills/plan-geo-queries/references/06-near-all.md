# `near_all`

**Use when:** Every subject feature must be near every simultaneous reference with AND semantics. Optionally rank by mean reference distance and keep the requested number of results.

**Do not use when:** Only one reference exists (`near`/`nearest_n`) or features must be near each other within the same subject layer (`cluster`). Never chain `nearest_n` for multi-reference proximity.

**Compose:** Use the latest subject-chain step as input. Omit an unstated distance so the contract supplies the default. Each named target needs its complete filter; a whole layer does not. Add every target layer to `context_layers`.
