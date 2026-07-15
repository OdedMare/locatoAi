# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

LocatoAI — a Geo-AI query application: users ask geographic questions in natural language (e.g. "Find schools near train stations in Tel Aviv"), scope them to a viewport or drawn polygon/rectangle, and a live LLM agent turns them into a validated geo query plan executed against GIS providers.

- `frontend/` — Next.js 16 (App Router) + TypeScript + Leaflet UI, plus a ⚙ settings panel (LLM key/model, PG connection, layers table).
- `backend/` — FastAPI + GeoPandas plan executor + **the FULL agent pipeline, live**: layer selection (call 1) → plan building (call 2) → validate → execute, all via an OpenAI-compatible LLM.

**Where we are:** the MVP works end to end with MQS and Cubes as the only production GIS providers. MQS enriches entities from `property_list`; Cubes infers arbitrary JSON schemas and WKT POINT locations dynamically. Provider geometry pushdown is always rechecked locally. Every setting has an `AILOCATOR_*` environment default and the Settings UI remains a live-override layer. Secrets are write-only. TLS verification defaults to enabled independently for both providers. Test GIS adapters live under `tests/` and are excluded from the non-root production image. **Known scaling risk:** MQS performs one detail request per entity. **Next candidates:** batched detail retrieval, multi-turn clarification, client timezone, and SSE streaming.

## Commands

```bash
# backend (requires local Postgres 'gis' DB — see below)
# Python runtime is EXACTLY 3.8.10 (requires-python pin). No local 3.8.10
# exists on ARM macs — use the Docker image:
cd backend
docker build --platform linux/amd64 -t ailocator-backend:py3.8.10 .   # build (amd64: no arm64 py3.8 geo wheels; rebuild after code/dep changes)
docker run -d --name ailocator-backend --platform linux/amd64 -p 8000:8000 \
  --add-host=pghost:host-gateway \
  -e AILOCATOR_DATABASE_URL=postgresql://$(whoami)@pghost:5432/gis \
  -v "$PWD/runtime-settings.json:/srv/backend/runtime-settings.json" \
  ailocator-backend:py3.8.10   # serve API (pghost = host PG; host.docker.internal breaks on IPv6)
# runtime-settings.json (UI-saved settings incl. API key) overrides env vars —
# it is mounted so settings survive container restarts. Its database_url must
# use pghost, not localhost.
docker run --rm --platform linux/amd64 ailocator-backend:py3.8.10 python -m pytest -q                 # run tests
docker run --rm --platform linux/amd64 ailocator-backend:py3.8.10 python -m pytest tests/test_executor.py::test_near_uses_meters_not_degrees  # single test
# quick iteration without rebuild: add -v "$PWD/app:/srv/backend/app" to the run command

# frontend
cd frontend
npm run dev      # dev server on http://localhost:3000 (proxies /api/* to :8000)
npm run build    # production build (also typechecks)
npm run lint     # ESLint
npx tsc --noEmit # typecheck only
```

Run backend and frontend together for the full flow; the frontend works standalone but Run Query shows a backend-unreachable error.

## Backend architecture (N-tier + SOLID)

**Full architecture explanation lives in `backend/README.md`** — keep it updated when structure changes. Summary:

Tiers under `backend/app/` — dependency direction is service → bl ← dal (DIP: `bl/ports.py` defines `LayersRepository`/`Provider`/`ProviderRegistry`/`LLMClient` protocols; the DAL implements them; `main.py` is the composition root that wires everything):

- `service/` — routers + DTOs only, no logic. `POST /api/query` (NL entry), `POST /api/execute-plan` (debug: run a hand-written plan), `POST /api/select-layers` (debug: agent call 1 only), `GET/PUT /api/settings` (backs the UI settings panel; secrets masked, responses include live catalog status), `GET /api/models` (live model ids from the configured OpenAI-compatible provider), and `GET/POST /api/layers` (browse/add catalog metadata).
- `bl/plan/` — **GeoQueryPlan is the core contract**: a 14-member discriminated union (`load`, `within_geometry`, `attribute_filter`, `near`, `nearest_n`, `near_all`, `cluster`, `between`, `crosses`, `touches`, `contains`, `directional`, `temporal_filter`, `count`; the three topological relations share a base model). Semantic validation enforces earlier references, catalog IDs, complete target filters, required boundaries, final output ordering, and terminal count.
- `bl/executor/` — engine dispatches via an op registry; each op is one self-registering module in `ops/` (OCP: new op = new file, engine untouched).
- `bl/agent/` — `select_layers.py` (call 1: catalog → prompt → layer ids; drops hallucinated ids, sanitizes/truncates catalog text per the untrusted-metadata rule) and `build_plan.py` (call 2: query + selected-layer schemas incl. sample field values → GeoQueryPlan; validate → retry once with the error → Hebrew clarify). Prompts are files in `prompts/`. `bl/query_orchestrator.py` owns the select → plan → execute flow with per-stage timings and summed token usage.
- `dal/` — `layers_repository.py` owns catalog SQL; `providers/mqs.py` enriches MQS entities; `providers/cubes.py` infers arbitrary Cubes JSON schemas and WKT POINT features; `llm/openai_client.py` implements the OpenAI-compatible LLM port. Production contains no mock provider.

**Layer catalog is Postgres**, not a file: table `public.layers` in the local `gis` DB (25 Hebrew layers; columns id/name/description/tags/provider/source_url). Plans reference layers by UUID.

**Settings precedence:** `AILOCATOR_*` env vars / `OPENAI_API_KEY` (`app/common/config.py`) are only DEFAULTS feeding `app/common/runtime_settings.py`; anything saved via the UI settings panel persists to `backend/runtime-settings.json` (gitignored, mounted into the container) and **overrides env**. Consumers read the store per call, so settings changes need no restart. Postgres host/port/database/user/password can be entered separately and override their corresponding values embedded in `database_url`; blank override fields fall back to the URL, and passwords are write-only in the API. The layers table name is identifier-validated + quoted before entering SQL.

**Locked decisions** (from the MVP guide — don't relitigate): agent emits plans, never SQL; meters math only after reprojecting to EPSG:2039 (`common/geo.py`), never in WGS84 degrees; provider metadata is untrusted input for prompts; clarify is a first-class response, not a confidence score.

**Test temporal data:** `data/accidents.geojson` uses `timestamp_offset_hours`; the test provider converts it relative to frozen `now` values.

Every request is logged to `backend/logs/requests.jsonl` (JSON lines).

## Frontend architecture

**The UI ↔ backend contract is exactly `{query, boundaries: MultiPolygon}`** — mirrored between `frontend/src/types/geo-query.ts` and `backend/app/service/dto.py`. Never change one side without the other. Geography modes (viewport bbox / drawn polygon / rectangle) all collapse into that required MultiPolygon before sending; viewport is the default.

**State flow:** `components/AppShell/index.tsx` is the single state owner (query text, geography mode, drawn shape, live map view, last request/response, settings visibility). It builds the request when the composer is submitted and calls `services/geoQueryService.ts`, which POSTs to `/api/query` (proxied to the backend via the rewrite in `next.config.ts` — no CORS involved). “New geo query” resets the conversation and geography state.

**UI layout:** the application UI is Hebrew-first and globally RTL (`<html lang="he" dir="rtl">`). Technical values such as URLs, credentials, provider names, model ids, table names, and JSON stay LTR. The chat workspace follows a ChatGPT-style structure: dark navigation/history sidebar + conversation surface + bottom composer. `QueryPanel` owns the layout only; `AgentTrace`, `ResultsPanel`, and `RequestPreview` render the assistant response, and `GeoQueryInput` remains a controlled input. Geography choices are compact chips above the composer. The other side remains the interactive map. Light/dark theme state lives in `AppShell`, follows the OS on first visit, persists as `locato-theme` in localStorage, and is applied through `data-theme` on `<html>`. Styling is centralized in `src/styles/globals.css`; icons come from `lucide-react`.

**Catalog UI:** `LayersPanel` browses/searches the PostgreSQL catalog, browses MQS inventory, can generate editable metadata suggestions from sampled entities, creates individual catalog rows, and can bulk-sync MQS. The browser only calls backend catalog endpoints; MQS and PostgreSQL remain server-side. New rows default to `provider="mqs"`.

**Component convention:** feature components normally live in their own folder under `src/components/` as `index.tsx`. MapWorkspace is the deliberate exception: its Leaflet-only helpers (`LeafletMap.tsx`, `MapGeoms.tsx`, `MapLayers.tsx`, `LayerPicker.tsx`, `consts.ts`) are colocated because they form one client-only map feature. (`SettingsPanel/` is the settings modal; it talks to `/api/settings` via `services/settingsService.ts` and mirrors `types/settings.ts` ↔ `settings_router.py`.)

**Map specifics** (`components/MapWorkspace/`):
- Leaflet touches `window` at import time, so `LeafletMap.tsx` is loaded via `next/dynamic` with `ssr: false` from the client component `index.tsx`. Don't import react-leaflet from server components.
- Coordinate order differs: GeoJSON/request objects use `[lng, lat]`; Leaflet uses `[lat, lng]`. Conversions happen inside the map components — keep them there.
- Drawing uses `leaflet-draw` through `react-leaflet-draw` (`MapGeoms`): selecting polygon/rectangle in the composer automatically enables that draw handler; the Leaflet toolbar remains available for redraws. Rectangle = click-drag; polygon = click points and close on the first point. Completed shapes are GeoJSON Polygons and are wrapped as MultiPolygons by `AppShell` before submission.
- Basemap switching is split between `LayerPicker`, `MapLayers`, and `consts.ts`. The current options are Esri World Imagery (“Orthophoto”) and OpenStreetMap streets. Tile attribution must stay accurate when adding or changing providers.
- `leaflet`, `leaflet-draw`, and their CSS must only enter through the dynamically loaded client map path. The drawing wrapper is pinned to `react-leaflet-draw@0.20.6` because the next release requires React 19 while this app uses React 18.

## Gotchas

- `frontend/AGENTS.md` warns that this Next.js version (16.x) may differ from training data — consult `frontend/node_modules/next/dist/docs/` before using Next APIs you're unsure about.
- Geodesic correctness matters later: never do meters math in WGS84 degrees (backend concern, but don't add naive distance logic to the UI either).
- **Python is pinned to exactly 3.8.10** (`requires-python ==3.8.10`): no `match`, no `X | Y` unions, no builtin generics (`list[str]`) in annotations pydantic/FastAPI evaluate — use `typing.Optional/Union/List/Dict` (`Annotated` from `typing_extensions`). The local 3.13 `.venv` is legacy; pip refuses to reinstall the project there — the Docker image is the runtime.
- The image must be built/run as **linux/amd64** — fiona ships no linux-arm64 wheels for py3.8 (fiona is pinned `<1.10`; 1.10 has no py3.8 wheels at all).
- Inside the container, host Postgres is `pghost` (via `--add-host=pghost:host-gateway`) — `host.docker.internal` resolves to an unreachable IPv6, and the URL needs an explicit user (container user is root).
- **Ollama must listen on all interfaces** for the container to reach it: `OLLAMA_HOST=0.0.0.0:11434 ollama serve` (default 127.0.0.1 binding is unreachable from Docker; exposes 11434 on the LAN while running). The LLM client has a degradation ladder for OpenAI-compat servers: JSON mode → plain → system prompt merged into the user turn.
- Layer-selection quality eval is SCORED: `backend/scripts/eval_select_layers.py` (20 Hebrew/English cases with expected layer sets incl. typos/slang/clarify cases; exit 1 on regression — run after every prompt/model change; currently 20/20). Add every real-world miss as a case. Downvotes from the UI's 👍/👎 land in the configured PostgreSQL feedback table (`POST /api/feedback`) — mine them for new cases.
- Selection returns a short Hebrew `reasoning` plus provider-reported prompt/completion/total token usage (shown in the UI Agent panel; omitted when the provider does not report usage).
- Catalog tags were LLM-enriched with bilingual aliases via `backend/scripts/enrich_layer_tags.py` (dry-run by default, `--apply` to write; pre-enrichment tags backed up in `backend/scripts/tags_backup.txt`). Rerun it after adding new layers.
