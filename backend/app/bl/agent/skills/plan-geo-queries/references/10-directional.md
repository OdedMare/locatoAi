# `directional`

**Use when:** Return the N geographically most northern, southern, eastern, or western subject features, such as “הכי צפוני”.

**Do not use when:** The request describes an entity's travel direction across time; use `movement_direction`.

**Emit:** `{"id":"s10","op":"directional","input":"s9","direction":"north|south|east|west","count":1}`

Use `count=1` for a singular extreme and the requested positive N otherwise. This ranks static feature locations after earlier filters.
