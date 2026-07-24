# `attribute_filter`

**Use when:** Restrict subject features by a real schema field and requested value or numeric comparison.

**Do not use when:** Filtering a named spatial reference; use that spatial operation's complete target filter instead. Do not guess fields or values—request `sample_field` when uncertain.

Use the latest subject-chain step as input. Use normalized `contains` for ordinary text, `fuzzy_contains` only for an apparent spelling or transliteration variant, and numeric operators only for numeric fields.
