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
- Keep HTTP calls in `src/services` and mirror backend DTOs in `src/types`.
- `AgentTrace` renders the public `pipeline_trace`, plan, tool calls, timings,
  selected layers, and feedback. It must support all 14 plan operations.
- Keep Leaflet and Leaflet Draw behind the dynamically imported client-only map
  path. GeoJSON is `[lng, lat]`; Leaflet positions are `[lat, lng]`.
- Keep the coordinate console top-center so it does not overlap the top-right layer
  picker. Supported copy formats are lat/lon, lon/lat, DMS, and WKT.
- Quick-question presets are intentionally absent. `RequestPreview` copies the full
  request/response/plan/trace debug bundle, and frontend failures go to the console.
- Preserve RTL defaults and mark URLs, identifiers, JSON, and credentials LTR.
- Keep the Settings UI: environment variables are deployment defaults and saved UI
  values are live overrides. Provider TLS verification must default to enabled.
- `LayersPanel` adds both FLAPI Cubes and Flow Packages. Packages discover typed
  parameters before execution and use `flapi://package/<id>` catalog sources.
