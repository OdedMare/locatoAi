---
name: plan-geo-queries
description: Route natural-language geographic requests to LocatoAI GeoQueryPlan operations and keep planning prompts, models, validators, executors, tests, and docs aligned. Use when adding, changing, debugging, reviewing, or explaining geo planning behavior involving boundaries, attributes, nearby or nearest searches, multi-reference proximity, same-layer clusters, between or topological relations, directional extremes, time ranges, moving entities, or counts.
---

# Plan Geo Queries

Choose the smallest valid operation chain that answers the request. Treat the Pydantic models, semantic validator, and executor as authoritative; prompt guidance helps selection but never replaces code enforcement.

## Workflow

1. Identify the subject layer whose features must be returned.
2. Separate constraints from reference layers: boundaries, time, attributes, spatial relations, moving-entity handling, and aggregation.
3. Read only the operation references needed for the request. When proximity wording is ambiguous, compare all four proximity references before choosing.
4. Compose operations in dependency order: `load` → required boundary → requested time/attributes → spatial relation → moving-entity collapse or movement → directional/terminal count.
5. Put spatial reference layers in `context_layers`; do not add unused `load` steps for references loaded internally by an operation.
6. Use `sample_field` for uncertain catalog values. Never invent a layer, field, value, or spatial reference.
7. When changing an operation, keep its model, validation, executor, skill reference, tests, both prompt profiles, frontend trace, and architecture docs synchronized.

## Operation routing

- Start a subject chain: [load](references/01-load.md)
- Enforce the request polygon: [within_geometry](references/02-within-geometry.md)
- Match a property: [attribute_filter](references/03-attribute-filter.md)
- Threshold distance to one other layer: [near](references/04-near.md)
- Rank the N closest to one other layer: [nearest_n](references/05-nearest-n.md)
- Require distance to every one of several references: [near_all](references/06-near-all.md)
- Find close groups inside the same layer: [cluster](references/07-cluster.md)
- Keep one newest observation per moving entity: [latest_per_entity](references/08-latest-per-entity.md)
- Detect movement or travel direction: [movement_direction](references/09-movement-direction.md)
- Compare different entities' trajectories in space and time: [trajectory_relation](references/17-trajectory-relation.md)
- Detect departure from or return to a starting place: [origin_movement](references/18-origin-movement.md)
- Select geographic extremes: [directional](references/10-directional.md)
- Find features in a corridor between references: [between](references/11-between.md)
- Match geometries whose interiors cross: [crosses](references/12-crosses.md)
- Match boundary-only contact: [touches](references/13-touches.md)
- Match input geometries containing references: [contains](references/14-contains.md)
- Restrict a temporal layer to a time window: [temporal_filter](references/15-temporal-filter.md)
- Return one terminal row count: [count](references/16-count.md)

## Important distinctions

- Use `near` for one reference and a distance threshold, `nearest_n` for a global top-N ranking, `near_all` for AND proximity to multiple references, and `cluster` for same-layer groups.
- Use `directional` for static geographic extremes and `movement_direction` for an entity's change across observations.
- Use `trajectory_relation` for relationships between different entities. Use `origin_movement` for one entity leaving its inferred starting place or returning to it.
- “Same destination” compares final positions and arrival times; “same place at different times” compares any visited positions with a minimum time separation.
- Use `between` for a buffered corridor; use `crosses`, `touches`, or `contains` only for exact topological relationships.
- For repeated moving observations, use the schema's declared `entity` and `time` roles. Clarify if a required role is absent.
- Apply `latest_per_entity` before returning, counting, or clustering distinct entities. Do not collapse observations before `movement_direction`, `trajectory_relation`, or `origin_movement`; each already returns one result row per matching entity.
