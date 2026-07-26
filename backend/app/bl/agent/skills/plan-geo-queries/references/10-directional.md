# `directional`

**Use when:** Return the N geographically most northern, southern, eastern, or western subject features.

**Do not use when:** The request describes an entity's travel direction across time; use `movement_direction`.

**Compose:** Use the latest subject-chain step as input. Omit `count` for a singular extreme and set the requested count otherwise. This ranks static locations after earlier filters.
