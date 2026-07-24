# `within_geometry`

**Use when:** `boundaries=yes`; put it immediately after the subject `load` to keep features intersecting the user polygon.

**Do not use when:** `boundaries=no`. Never invent geometry or apply this to separately loaded reference layers.

Use the latest subject-chain step as input. The operation uses intersection, so lines or polygons partially inside the boundary still match.
