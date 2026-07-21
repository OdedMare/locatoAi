# `within_geometry`

**Use when:** `boundaries=yes`; put it immediately after the subject `load` to keep features intersecting the user polygon.

**Do not use when:** `boundaries=no`. Never invent geometry or apply this to separately loaded reference layers.

**Emit:** `{"id":"s2","op":"within_geometry","input":"s1","geometry":"user_polygon"}`

The operation uses intersection, so lines or polygons partially inside the boundary still match. A request with boundaries is invalid without this step.
