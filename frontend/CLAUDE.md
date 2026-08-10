@AGENTS.md

# Frontend development context

This is the Next.js 16 / React 18 Hebrew-first RTL client for LocatoAI. Read
[`README.md`](README.md) for the current component tree, state ownership, API
surface, and map behavior; read the root [`CLAUDE.md`](../CLAUDE.md) for the
full backend pipeline and repository-wide constraints.

- `AppShell` owns shared query, geography, map, response, dialog, theme, and up to
  eight completed in-memory chat turns. A direct clarification reply carries the
  immediately preceding request as textual context; there is no server-side session.
- Every query sends exactly `{query, boundaries}` with a required GeoJSON
  `MultiPolygon`; the supported scopes are viewport, polygon, and rectangle.
- Keep HTTP calls behind `src/services/api.ts`, which traces timing, redacts secrets,
  and normalizes FastAPI error bodies; mirror backend DTOs in `src/types`.
- `useQueryRunPolling.ts` owns the non-overlapping 1.5-second poll and timer cleanup.
  `AgentTrace` renders its live `pipeline_trace`, then the final plan, tool calls,
  timings, selected layers, and feedback. It must support all 18 plan operations.
- Keep Leaflet and Leaflet Draw behind the dynamically imported client-only map
  path. GeoJSON is `[lng, lat]`; Leaflet positions are `[lat, lng]`.
- Keep the coordinate console top-center so it does not overlap the top-right layer
  picker. Supported copy formats are lat/lon, lon/lat, DMS, and WKT.
- Quick-question presets are intentionally absent. `RequestPreview` copies the full
  request/response/plan/trace debug bundle, and frontend failures go to the console.
- `services/queryDebugLog.ts` mirrors the whole backend pipeline into the DevTools
  console: `.completed` prints a collapsed group with timings, tokens, selected layers,
  plan, and a `console.table` of the trace, re-logging every failed entry with its
  `error_type`/`error`. Backend
  `ProviderError` text (e.g. a FLAPI package rejection) reaches it verbatim through the
  executor's per-step failed trace.
- Preserve RTL defaults and mark URLs, identifiers, JSON, and credentials LTR.
- `AgentStudioPanel` edits the `area-summary` profile's numbered
  `## Workflow` section through accessible add/delete/reorder controls; the
  generated Markdown remains the persisted source of truth. New skills can start
  from the generic summary template, which adds an editable `## Summary target`;
  step-level parallel eligibility is encoded as the model-facing `[parallel]`
  marker. The current `GeoQueryPlan` executor remains sequential.
- Keep the Settings UI: environment variables are deployment defaults and saved UI
  values are live overrides. Provider TLS verification must default to enabled.
- `LayersPanel` adds Flow Packages via `flapi://package/<id>` catalog sources,
  configured through the four cube fields only. There is no per-parameter form and no
  hand-entered WKT/geometry: flunks owns the request, and a geo package receives the
  query boundary automatically. The sample-polygon picker appears for the `geo` input
  kind, which needs a boundary to sample metadata.
