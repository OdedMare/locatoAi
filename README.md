# LocatoAI

LocatoAI is a Hebrew-first geographic assistant. A user asks a geographic question in natural language, optionally limits it to the visible map or a drawn polygon, and receives mapped GIS features or a scalar count. The system uses an LLM only to select known data layers and build a constrained query plan; deterministic Python code validates and executes that plan.

This README explains the whole system. More detailed guides live in [backend/README.md](backend/README.md), [frontend/README.md](frontend/README.md), and [backend/app/bl/agent/prompts/README.md](backend/app/bl/agent/prompts/README.md).

## System at a glance

```text
Browser
  │
  │ Hebrew/English query + optional GeoJSON MultiPolygon
  ▼
Next.js 16 / React 18 frontend
  │  /api/* rewrite (same-origin browser requests)
  ▼
FastAPI service tier
  ▼
QueryOrchestrator
  ├─ 1. read PostgreSQL layer catalog
  ├─ 2. LLM selects catalog layers
  ├─ 3. providers describe selected schemas
  ├─ 4. LLM builds a typed GeoQueryPlan
  ├─ 5. semantic validation; one correction attempt if invalid
  └─ 6. GeoPandas executor runs deterministic operations
        │
        ├─ PostgreSQL: catalog, runtime-selected table, feedback
        ├─ MQS REST API: production GIS schemas and features
        └─ OpenAI-compatible API: Ollama/Gemma or another model server
  ▼
GeoJSON FeatureCollection or integer count
  ▼
Agent trace + result table + Leaflet map
```

The main trust boundary is deliberate: the model never receives database credentials, never writes SQL, and never directly accesses GIS services. It can only return JSON matching the plan contract. Catalog IDs, step references, boundary requirements, and operation limits are checked before execution.

## Repository layout

```text
locatoAi/
├── README.md                         # whole-system architecture and setup
├── CLAUDE.md                         # repository development guidance
├── backend/
│   ├── app/
│   │   ├── main.py                   # composition root and FastAPI app
│   │   ├── service/                  # HTTP routers and DTO translation
│   │   ├── bl/                       # business rules, agents, plans, executor
│   │   ├── dal/                      # PostgreSQL, MQS, and LLM adapters
│   │   └── common/                   # settings, errors, CRS, logging
│   ├── data/                         # local GeoJSON test fixtures
│   ├── scripts/                      # evaluation and tag enrichment tools
│   ├── tests/                        # isolated business/provider tests
│   ├── Dockerfile
│   └── README.md                     # backend deep dive
└── frontend/
    ├── src/app/                      # Next.js App Router entry points
    ├── src/components/               # query, map, results, catalog, settings UI
    ├── src/services/                 # typed HTTP boundary
    ├── src/types/                    # frontend mirrors of backend contracts
    ├── src/styles/                   # global responsive RTL/light/dark styling
    ├── next.config.ts                # /api proxy to FastAPI
    └── README.md                     # frontend deep dive
```

## End-to-end query stages

1. The user enters a question in `GeoQueryInput`.
2. `AppShell` combines the text with one of four geography modes: no boundary, current viewport, polygon, or rectangle.
3. Polygon and viewport shapes are normalized to GeoJSON `MultiPolygon`, producing exactly `{query, boundaries}`.
4. `geoQueryService` posts the request to `/api/query`. Next.js rewrites it to the FastAPI backend configured by `BACKEND_URL`.
5. FastAPI validates the transport DTO and converts a boundary to a Shapely geometry.
6. `LayerSelector` reads layer metadata from the PostgreSQL catalog, sanitizes it, and asks the configured model to return known layer IDs or a short Hebrew clarification.
7. `PlanBuilder` obtains provider schemas and sample values for the selected layers. The model may request up to two additional `sample_field` rounds.
8. The model returns a `GeoQueryPlan`. Pydantic validates its shape; semantic validation checks references, catalog IDs, boundary use, and terminal count rules. An invalid model response gets one correction attempt.
9. `PlanExecutor` runs the steps in order. It resolves features through a provider registry and dispatches each operation through an operation registry.
10. The backend returns GeoJSON features or `scalar_result`, plus the plan, selected layers, reasoning, timing, token usage, and tool calls.
11. The frontend shows the agent trace and results. GeoJSON is drawn with Leaflet and the map fits the result bounds.
12. A thumbs-up/down vote posts the selection context to the configurable PostgreSQL feedback table.

Clarification is a successful product outcome, not an exception. Either agent stage can return `status: "clarify"` when the request is ambiguous or unsupported. Infrastructure and domain failures use typed errors mapped to HTTP status codes.

## Architectural boundaries

The backend follows `service → business logic ← data access`:

- `service/` owns HTTP details only.
- `bl/` owns the domain contracts and orchestration.
- `dal/` implements interfaces owned by `bl/ports.py`.
- `main.py` is the only composition root that creates concrete adapters and connects them.

The frontend follows one-way state flow:

- `AppShell` owns cross-component application state.
- Presentational/workspace components receive values and callbacks.
- `services/` is the only browser-to-backend boundary.
- `types/` mirrors public backend DTOs and contains GeoJSON conversion helpers.
- Leaflet is dynamically imported because it depends on browser globals.

## Core data contracts

### Query request

```json
{
  "query": "מצא את שלושת בתי הספר הקרובים ביותר לכיכר",
  "boundaries": null
}
```

`boundaries` is either `null` or a GeoJSON `MultiPolygon` in longitude/latitude order.

### Query response

The common response includes:

- `status`: `ok`, `clarify`, or `error`.
- `features`: GeoJSON `FeatureCollection` for spatial results.
- `scalar_result`: integer for a terminal `count` plan.
- `plan`: the validated plan that was executed.
- `selected_layers` and `reasoning`: inspectable layer-selection trace.
- `tool_calls`: any schema value sampling requested by the model.
- `timing_ms`: select, plan, and execute stage timings.
- `token_usage`: summed usage from model calls when the provider reports it.

### GeoQueryPlan

A plan is an ordered DAG. Each step has a unique ID, and any `input` must refer to an earlier step. The currently supported operations are:

| Operation | Result |
|---|---|
| `load` | Loads a catalog layer through its registered provider. |
| `within_geometry` | Keeps features intersecting the user boundary. |
| `attribute_filter` | Applies `eq`, `neq`, `gt`, `lt`, or `contains`. |
| `near` | Keeps features within a maximum metric distance of a target layer. |
| `nearest_n` | Returns the globally nearest N input features to a target layer. |
| `directional` | Returns northernmost, southernmost, easternmost, or westernmost features. |
| `temporal_filter` | Filters using the provider-declared temporal field. |
| `count` | Returns a terminal integer count. |

All meter calculations reproject to Israel TM `EPSG:2039`; API boundaries and returned results use WGS84.

## Data and external systems

### PostgreSQL

One runtime-configurable connection is shared by:

- The layer catalog table, default `public.layers`.
- The feedback table, default `public.feedback`, created on first feedback if absent.

The catalog stores metadata, not feature bodies: ID, name, description, tags, provider, and source URL. Table identifiers accept only a safe `table` or `schema.table` form and are quoted before SQL interpolation. Credentials may be supplied in the URL or as host/port/database/user/password overrides.

### MQS

MQS is the production feature provider. Catalog entries use `provider="mqs"` and normally store a stable source such as `mqs://layer/<id>`. The live base URL comes from runtime settings. MQS supplies inventory metadata, layer schemas, sample values, and paginated features; spatial filtering is performed locally by the executor.

### LLM provider

The LLM client uses an OpenAI-compatible API. The default points to local Ollama and model `gemma4:31b-cloud`, but model, base URL, and optional key are runtime editable. The client progressively falls back from JSON response mode when a compatible server implements a smaller subset of the OpenAI API.

### Map tiles

The UI offers Esri World Imagery and OpenStreetMap base layers. These browser-side tile requests are separate from the catalog/provider architecture used for query data.

## Configuration model

Backend configuration has two layers:

1. Environment defaults loaded by Pydantic settings. Most use the `AILOCATOR_` prefix; `OPENAI_API_KEY` is accepted directly.
2. UI overrides persisted to `backend/runtime-settings.json` (or `AILOCATOR_RUNTIME_SETTINGS_FILE`). Saved values win over environment defaults.

Database, table, LLM, and MQS settings are read from the runtime store on every relevant call, so a saved change does not require a backend restart. API keys and database passwords are never returned to the browser; settings responses expose only presence flags and masked hints.

The frontend accepts:

- `BACKEND_URL`, used server-side by the Next.js rewrite and defaulting to `http://127.0.0.1:8000`.

## Local development

### 1. Start PostgreSQL and supporting services

Create a PostgreSQL database (the default is `gis`) and a layer catalog table matching the columns used by `PostgresLayersRepository`: `id`, `name`, `description`, `tags`, `provider`, and `source_url`. Configure an MQS URL and an OpenAI-compatible model server through environment variables or the UI settings panel.

### 2. Start the backend

The backend targets Python `3.8.10` exactly:

```bash
cd backend
python3.8 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Health check: `GET http://127.0.0.1:8000/health`.

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. Browser calls to `/api/*` are proxied to port 8000 by default.

### Docker backend

The geospatial Python stack is built for Linux AMD64:

```bash
cd backend
docker build --platform linux/amd64 -t locato-backend .
docker run --rm --platform linux/amd64 -p 8000:8000 \
  --add-host=pghost:host-gateway \
  -e AILOCATOR_DATABASE_URL=postgresql://user:password@pghost:5432/gis \
  locato-backend
```

## Testing and quality

Backend tests use in-memory repositories, a mock provider, mock HTTP transports, and local GeoJSON so most business logic runs without PostgreSQL, MQS, or an LLM:

```bash
cd backend
.venv/bin/pytest -q
```

Frontend checks:

```bash
cd frontend
npm run lint
npm run build
```

Layer-selection quality is covered by `backend/scripts/eval_select_layers.py`. Prompt changes should be evaluated against its Hebrew/English cases. Real user votes are stored in PostgreSQL and can seed future regression cases.

## Extension map

- Add a plan operation: define its Pydantic step, add semantic checks if needed, create a registered handler under `backend/app/bl/executor/ops/`, import it in the operations package, and mirror the type/description in the frontend trace.
- Add a GIS provider: implement the small `Provider` protocol, register it in `main.py`, and write catalog rows using its provider name.
- Add an API endpoint: add a router in `service/`, mount it in `main.py`, and mirror its DTO in `frontend/src/types` if the UI consumes it.
- Add a frontend workflow: keep cross-workspace state in `AppShell`, HTTP details in `services/`, and contract types synchronized with backend DTOs.
- Tune the agent: edit the prompt files and run the scored evaluation; keep validation and execution rules in code.

## Current limitations

- Clarification is single-turn; the next message does not yet carry conversation history.
- MQS uses fetch-all-then-filter-locally with a 50,000-feature safety cap.
- Runtime settings persist to a local JSON file and are not multi-user settings.
- There is no streaming progress channel; the UI shows a single loading phase.
- The production provider registry currently registers MQS only. The ArcGIS adapter is a local test fixture.
