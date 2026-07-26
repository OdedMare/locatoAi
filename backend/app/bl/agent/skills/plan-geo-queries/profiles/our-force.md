# OurForce mission profile

Use the selected layer tagged `profile:our-force` as the subject/output source when the user asks about our forces, units, soldiers, platforms, or call signs. Treat other selected layers as spatial references when the request asks what is nearby or between places.

Build the subject chain as `load` → boundary when present → explicitly requested time and attribute constraints → requested spatial operation → `latest_per_entity` when returning current distinct entities. Use the layer schema's declared `entity` and `time` roles; if either required role is absent, clarify instead of guessing.

Map force types, unit names, and call signs to actual schema fields and sampled values. Do not hard-code a field name or catalog id. When no time window is requested, do not invent one; preserve the provider's configured default window.

For counts, collapse repeated observations before `count`. For movement and trajectory operations, keep the complete observation history and do not add `latest_per_entity`.
