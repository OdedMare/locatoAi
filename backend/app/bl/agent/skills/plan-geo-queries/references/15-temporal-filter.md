# `temporal_filter`

**Use when:** Restrict a layer with provider-declared temporal metadata to an inclusive ISO-8601 time range requested by the user.

**Do not use when:** The layer has no declared `time` role or the user did not request a time restriction. Preserve provider behavior when no window is requested.

**Compose:** Resolve relative dates from `UTC now`. Put this before movement or trajectory analysis and before collapsing repeated observations.
