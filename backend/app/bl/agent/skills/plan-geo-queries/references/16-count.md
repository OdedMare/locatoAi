# `count`

**Use when:** The user asks “how many/כמה” and needs one row count after all requested filtering and distinct-entity handling.

**Do not use when:** The user asks to show N results; use the relevant operation's result limit. This operation does not group or count by an attribute.

**Emit:** `{"id":"s16","op":"count","input":"s15"}`

Make `count` the final step and plan `output`; no later step may consume it. For repeated moving entities, apply `latest_per_entity` first so each entity counts once.
