# `attribute_filter`

**Use when:** Restrict subject features by a real schema field and requested value or numeric comparison.

**Do not use when:** Filtering a named spatial reference; use that spatial operation's complete target filter instead. Do not guess fields or values—request `sample_field` when uncertain.

**Emit:** `{"id":"s3","op":"attribute_filter","input":"s2","field":"field","operator":"eq|neq|gt|lt|contains|fuzzy_contains","value":"string-or-number"}`

Use normalized `contains` for ordinary text. Use `fuzzy_contains` only for an apparent typo or spelling/transliteration variant. Use `gt`/`lt` only for numeric comparisons and match the samples' language and format.
