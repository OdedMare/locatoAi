# `temporal_filter`

**Use when:** Restrict a layer with provider-declared temporal metadata to an inclusive ISO-8601 time range requested by the user.

**Do not use when:** The layer has no temporal field or the user did not request a time restriction. Do not invent a wider Tyche window when none is requested; preserve its provider lookback.

**Emit:** `{"id":"s15","op":"temporal_filter","input":"s14","from":"ISO-8601","to":"ISO-8601"}`

Resolve relative dates from `UTC now`; “yesterday/אתמול” is the complete previous UTC calendar day. Put this before `movement_direction` and before collapsing moving observations.
