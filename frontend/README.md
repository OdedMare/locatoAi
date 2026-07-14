# LocatoAI Frontend

The frontend is a Hebrew RTL, map-centered client for the LocatoAI geographic query service. It is built with Next.js 16 App Router, React 18, TypeScript, Leaflet, React Leaflet, and Leaflet Draw. It owns query composition and presentation; geographic planning and execution remain in the backend.

See the [root README](../README.md) for the whole system and [backend README](../backend/README.md) for the API and execution pipeline.

## Responsibilities

The frontend:

- Collects a Hebrew or English natural-language query.
- Lets the user scope it globally, to the current viewport, or to a drawn polygon/rectangle.
- Normalizes UI geometry into the backend's GeoJSON `MultiPolygon` contract.
- Calls the backend through same-origin `/api/*` routes.
- Presents selected layers, model reasoning, tool calls, plans, timing, and token use.
- Renders spatial results in a table and on an interactive map.
- Renders scalar count results without expecting GeoJSON.
- Provides searchable layer catalog and remote MQS browsing workflows.
- Provides live-editable LLM, MQS, PostgreSQL, and table settings.
- Persists light/dark theme preference in browser local storage.
- Sends thumbs-up/down feedback to backend PostgreSQL persistence.

It does not select layers, construct plans, validate plans, execute spatial operations, connect to PostgreSQL, or call MQS directly.

## Runtime architecture

```text
src/app/layout.tsx
  └─ global RTL document + global CSS
     src/app/page.tsx
       └─ AppShell (client-side state owner)
          ├─ QueryPanel
          │  ├─ navigation / dialogs / theme actions
          │  ├─ GeoQueryInput
          │  ├─ GeographyControls
          │  ├─ AgentTrace → feedbackService
          │  ├─ ResultsPanel
          │  └─ RequestPreview
          ├─ SettingsPanel → settingsService
          ├─ LayersPanel → catalogService
          └─ MapWorkspace
             └─ dynamic LeafletMap (SSR disabled)
                ├─ MapLayers + LayerPicker
                ├─ ViewReporter
                ├─ MapGeoms
                └─ MapResults
```

`AppShell` is the state boundary. There is no global application store: props and callbacks make data flow explicit and keep the current single-page workflow easy to trace.

## Application state

`AppShell` owns:

| State | Purpose |
|---|---|
| `queryText` | Current composer text. |
| `geographyMode` | `none`, `viewport`, `polygon`, or `rectangle`. |
| `drawnGeometry` | Last drawn GeoJSON Polygon. Cleared when mode changes. |
| `mapView` | Live map center, zoom, and bounding box. |
| `lastRequest` | Exact query DTO sent to the backend and shown in debug UI. |
| `lastResponse` | Backend response used by trace, results, and map. |
| `isSubmitting` | Prevents duplicate submissions and drives loading UI. |
| Dialog flags | Settings and layer-browser visibility. |
| `isDarkMode` | Theme state synchronized with `data-theme` and local storage. |

Component-local state is used for modal forms, catalog searches, feedback voting, map base-layer choice, and drawing internals.

## Query lifecycle

1. `GeoQueryInput` edits `queryText`; Cmd/Ctrl+Enter or the send button triggers submission.
2. `GeographyControls` chooses scope:
   - `none`: sends `boundaries: null`.
   - `viewport`: converts the current Leaflet bounding box to a rectangular MultiPolygon.
   - `polygon` or `rectangle`: Leaflet Draw produces a Polygon, then `polygonToMultiPolygon` wraps it for the API.
3. `AppShell.buildRequest()` creates exactly `{query, boundaries}` and stores it as `lastRequest`.
4. `geoQueryService.submitQuery()` posts JSON to `/api/query`.
5. While waiting, `AgentTrace` shows the selection loading state.
6. When the response arrives:
   - `AgentTrace` resolves plan layer IDs to selected layer names and displays selection reasoning, sampled fields, the plan, timing, and token use.
   - `ResultsPanel` shows a clarification, error, scalar count, or feature-property table.
   - `MapResults` renders feature geometry and fits the map to its bounds.
   - `RequestPreview` displays the exact request and response metadata.
7. Voting calls `feedbackService`; failure is intentionally non-blocking for the main query experience.

Network failures and non-2xx query responses are normalized by `geoQueryService` into `status: "error"`, giving components one stable response shape.

## Map architecture

Leaflet reads `window` during import, so `MapWorkspace` loads `LeafletMap` with `ssr: false`.

- `ViewReporter` listens for `moveend` and reports `[minLng, minLat, maxLng, maxLat]` to `AppShell`.
- `MapGeoms` imperatively activates the correct Leaflet Draw tool when geography mode changes. Only one drawn boundary is retained.
- `MapResults` uses an imperative `L.geoJSON` layer because React Leaflet's GeoJSON component does not reliably update when data changes. It styles points and shapes, binds a popup when a feature has `properties.name`, and removes the old result layer during effect cleanup.
- `MapLayers` renders the selected base tile layer.
- `LayerPicker` switches between Esri World Imagery and OpenStreetMap.

Coordinates in frontend GeoJSON are always `[longitude, latitude]`; Leaflet component centers use `[latitude, longitude]`, so conversion is explicit at the map boundary.

## Component guide

### `AppShell`

The page controller and sole owner of shared state. It builds backend requests, submits queries, coordinates dialogs, resets a new query, and chooses which response features reach the map.

### `QueryPanel`

The chat-style left workspace. It composes navigation, welcome/conversation states, the query composer, geography controls, agent trace, results, and request preview.

### `AgentTrace`

The explainability surface. It displays selected catalog layers and tags, layer-selection reasoning, plan steps translated into Hebrew, `sample_field` calls, selection timing, aggregate token usage, and feedback controls.

### `ResultsPanel`

Handles every response state. Feature results become a dynamic property table capped at 20 visible rows. When `distance_to_target_m` exists, rows are sorted nearest-first and distance is formatted in meters. A terminal count uses `scalar_result` instead.

### `LayersPanel`

Loads and searches catalog metadata. It supports manual layer creation and browsing remote MQS inventory before copying a remote layer into the creation form. Selecting a remote layer automatically asks the backend to sample up to 10 random entities and generate a description and tags; the suggestions populate normal editable fields and are not saved until the user submits the form. Catalog writes go through backend endpoints; this component never talks to PostgreSQL or MQS itself.

### `SettingsPanel`

Loads runtime settings, populates editable LLM/MQS/database/table fields, probes available models using unsaved form values, and persists a partial update. Empty API key and database password fields mean “keep the saved secret.” The response includes a live catalog connection status.

### `RequestPreview`

A developer-oriented transparency panel showing the exact structured request and backend status/timing.

## Source layout

```text
src/
├── app/
│   ├── layout.tsx              # metadata, Hebrew language, RTL direction, CSS
│   └── page.tsx                # renders AppShell
├── components/
│   ├── AppShell/               # shared state and orchestration
│   ├── QueryPanel/             # chat/navigation composition
│   ├── GeoQueryInput/          # text input and examples
│   ├── GeographyControls/      # query-boundary mode
│   ├── AgentTrace/             # agent observability and votes
│   ├── ResultsPanel/           # feature/scalar result rendering
│   ├── RequestPreview/         # raw request/status debug view
│   ├── LayersPanel/            # local catalog + remote MQS browser
│   ├── SettingsPanel/          # live backend configuration
│   └── MapWorkspace/           # dynamic Leaflet integration
├── services/
│   ├── geoQueryService.ts      # POST /api/query
│   ├── catalogService.ts       # catalog CRUD, remote browse, synchronization
│   ├── settingsService.ts      # settings and model probing
│   └── feedbackService.ts      # POST /api/feedback
├── types/
│   ├── geo-query.ts            # request/response/plan/map contracts + geometry helpers
│   ├── catalog.ts              # catalog API mirrors
│   └── settings.ts             # settings API mirrors
└── styles/globals.css          # layout, responsive behavior, RTL, themes
```

## API boundary

`next.config.ts` rewrites `/api/:path*` to `${BACKEND_URL}/api/:path*`. The browser therefore uses same-origin URLs and does not need backend CORS configuration.

| Service | Backend endpoint | Use |
|---|---|---|
| `submitQuery` | `POST /api/query` | Run the complete natural-language pipeline. |
| `getLayers` | `GET /api/layers` | Read catalog metadata. |
| `getMqsLayers` | `GET /api/layers/mqs` | Browse remote inventory without writing. |
| `createLayer` | `POST /api/layers` | Add one catalog entry. |
| `generateLayerMetadata` | `POST /api/layers/generate-metadata` | Generate editable metadata from a random entity sample. |
| `syncMqsLayers` | `POST /api/layers/sync-mqs` | Bulk upsert remote inventory. |
| `getSettings` | `GET /api/settings` | Load settings and catalog status. |
| `updateSettings` | `PUT /api/settings` | Save validated runtime overrides. |
| `getModels` | `POST /api/models` | Probe a saved or unsaved LLM endpoint. |
| `submitFeedback` | `POST /api/feedback` | Persist a thumbs verdict. |

The TypeScript interfaces intentionally mirror Pydantic DTOs. When an API contract changes, update both sides in the same change.

## Styling and directionality

The document root is `lang="he" dir="rtl"`. Inputs and technical values selectively use `dir="ltr"` or `dir="auto"`. Global CSS contains desktop layout, responsive breakpoints, modal styling, map controls, and theme overrides driven by `:root[data-theme="dark"]`.

Theme initialization considers `localStorage["locato-theme"]`, then the operating-system preference. The preference is stored whenever it changes.

## Running

Requirements: a supported Node.js runtime, npm, and the FastAPI backend.

```bash
npm install
npm run dev
```

Open `http://localhost:3000`. To target a different backend:

```bash
BACKEND_URL=http://127.0.0.1:9000 npm run dev
```

Production checks and runtime:

```bash
npm run lint
npm run build
npm run start
```

Remote map tiles require browser network access to Esri and OpenStreetMap tile hosts.

## Adding or changing frontend behavior

- Keep backend DTO mirrors in `src/types`; avoid untyped response access in components.
- Put HTTP calls and response error normalization in `src/services`.
- Put state shared by the query and map workspaces in `AppShell`.
- Keep browser-only libraries behind client components and, when they touch globals at import time, dynamic imports with SSR disabled.
- When adding a backend plan operation, update `GeoPlanStep` and `AgentTrace.describeStep` so users can inspect it.
- Preserve `[lng, lat]` in GeoJSON and convert only at Leaflet APIs that expect `[lat, lng]`.
- Preserve Hebrew RTL defaults while marking identifiers, URLs, and numeric technical values with the appropriate direction.

## Current limitations

- Only the most recent request/response is kept; the “history” is not persistent chat history.
- Clarification responses are not automatically threaded into a follow-up request.
- Query progress is not streamed by stage.
- There is no dedicated frontend test suite yet; lint, TypeScript checking, and production build are the current automated frontend gates.
- The result table shows at most 20 rows, while the map may display the full returned collection.
