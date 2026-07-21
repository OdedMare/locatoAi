---
name: locate-our-forces-nearby
description: Tune or review LocatoAI layer selection, GeoQueryPlan prompts, tests, and provider behavior for the primary mission of locating OurForce entities from Tyche near MQS/Cubes context. Use for OurForce, soldier, tank, unit, call-sign, nearby-landmark, Tyche-led proximity, or mission-query changes while preserving generic provider behavior.
---

# Locate Our Forces Nearby

Apply a mission-specific provider strategy without weakening LocatoAI's generic GIS flow.

## Workflow

1. Read the root `CLAUDE.md` and every `CLAUDE.md` governing touched files.
2. Trace selection → plan building → validation → execution before editing.
3. Preserve all generic MQS, Cubes, Tyche, and non-OurForce query behavior.
4. Update full and diet prompts together. Keep code validation authoritative.
5. Add the smallest regression check and run the relevant prompt/unit evaluation.

## Provider roles

- Treat the catalog `tyche` כוחותינו/OurForce layer as the subject and output source
  when the requested entity is one of our forces: soldier, tank, unit, force type,
  call sign, or another OurForce identity.
- Treat matching `mqs` or `cubes` layers as spatial references for named nearby places,
  objects, infrastructure, or events.
- Derive roles from provider metadata; never hardcode catalog UUIDs.
- Keep normal subject/reference selection for requests unrelated to OurForce.
- Clarify instead of returning a partial plan when a required subject or reference
  layer is missing.

## Mission plan recipe

Build the subject chain in this order when the query asks where an OurForce entity is
relative to context:

1. `load` the Tyche subject.
2. Apply `within_geometry` when request boundaries exist.
3. Apply the user's `temporal_filter`; without one, preserve Tyche's one-hour lookback.
4. Filter force type, unit, call sign, or identity using schema fields and sampled values.
5. Apply `near`, `near_all`, or `between` against MQS/Cubes references.
6. Apply `latest_per_entity` by `netId`/`eventTime` before returning or counting.

For movement requests, use `movement_direction` after boundary/time/attribute filters;
do not also apply `latest_per_entity`. Put reference ids in `context_layers`; spatial
operations load their targets internally. Named targets require their complete
field/operator/value filter. Use `sample_field` rather than guessing.

## Verification

- Confirm both prompt profiles expose provider metadata and retain every operation.
- Run focused selection/build-plan tests.
- Run `backend/scripts/eval_select_layers.py` when the configured catalog and LLM are
  available; add real mission misses as cases.
