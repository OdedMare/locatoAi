# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

LocatoAI — a Geo-AI query application: users ask geographic questions in natural language (e.g. "Find schools near train stations in Tel Aviv"), optionally scope them to a map area, and (in future stages) an LLM agent turns them into a validated geo query plan executed against GIS providers.

- `frontend/` — Next.js 16 (App Router) + TypeScript + Leaflet UI, plus a ⚙ settings panel (LLM key/model, PG connection, layers table).
- `backend/` — FastAPI + GeoPandas plan executor (plan-in → GeoJSON-out, fully tested) + the agent's **call 1 (layer selection), which is live** via an OpenAI-compatible LLM.

**Where we are / next step:** executor ✅, settings system ✅, layer selection ✅ **live and eval-passing (10/10, 1–7s/query)**. **The main model is Gemma 4 31B via Ollama cloud** (`llm_model: gemma4:31b-cloud`, `llm_base_url: http://pghost:11434/v1` in runtime-settings — no API key; the LLM client is key-optional when a base_url is set; requires the host to be `ollama signin`-ed once). Batch eval: `docker exec ailocator-backend python scripts/eval_select_layers.py`. **Clarify questions are ALWAYS Hebrew** (product decision — enforced in `prompts/select_layers.md` and the `_FALLBACK_CLARIFY` constant). **Next: agent call 2 (`bl/agent/build_plan.py`)** — query + selected-layer schemas → GeoQueryPlan JSON → validate (retry once with the error appended, then clarify) → execute, all inside `bl/query_orchestrator.py.run_query` where a `NEXT STAGE` comment marks the spot. Until then `POST /api/query` answers with a clarify naming the selected layers.

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

Tiers under `backend/app/` — dependency direction is service → bl ← dal (DIP: `bl/ports.py` defines `LayersRepository`/`Provider`/`ProviderRegistry` protocols; the DAL implements them; `main.py` is the composition root that wires everything):

- `service/` — routers + DTOs only, no logic. `POST /api/query` (NL entry: runs layer selection, plan building pending), `POST /api/execute-plan` (debug: run a hand-written plan — real, tested), `POST /api/select-layers` (debug: agent call 1 only), `GET/PUT /api/settings` (backs the UI settings panel; secrets masked, responses include live catalog status).
- `bl/plan/` — **GeoQueryPlan is the core contract**: discriminated union of 6 step types (`load`, `within_geometry`, `attribute_filter`, `near`, `directional`, `temporal_filter`), semantic validation in `validators.py` (refs must point to earlier steps, so list order is execution order).
- `bl/executor/` — engine dispatches via an op registry; each op is one self-registering module in `ops/` (OCP: new op = new file, engine untouched).
- `bl/agent/` — `select_layers.py` (live: catalog → prompt → layer ids; drops hallucinated ids, sanitizes/truncates catalog text per the untrusted-metadata rule; prompt is a file in `prompts/`), `build_plan.py` (stub — the next task). `bl/query_orchestrator.py` owns the select → plan → validate → execute flow and the retry/clarify policy.
- `dal/` — `layers_repository.py` (the only SQL) + `providers/arcgis_mock.py` (serves `data/*.geojson`, file picked by the source_url's last path segment) + `llm/openai_client.py` (JSON-mode chat client behind the `LLMClient` port: reads model/key/base_url from the settings store on every call, strips ``` fences, retries once on bad JSON, falls back when a server rejects `response_format`).

**Layer catalog is Postgres**, not a file: table `public.layers` in the local `gis` DB (25 Hebrew layers; columns id/name/description/tags/provider/source_url). Plans reference layers by UUID.

**Settings precedence:** `AILOCATOR_*` env vars / `OPENAI_API_KEY` (`app/common/config.py`) are only DEFAULTS feeding `app/common/runtime_settings.py`; anything saved via the UI settings panel persists to `backend/runtime-settings.json` (gitignored, mounted into the container) and **overrides env**. Consumers read the store per call, so settings changes need no restart. The layers table name is identifier-validated + quoted before entering SQL.

**Locked decisions** (from the MVP guide — don't relitigate): agent emits plans, never SQL; meters math only after reprojecting to EPSG:2039 (`common/geo.py`), never in WGS84 degrees; provider metadata is untrusted input for prompts; clarify is a first-class response, not a confidence score.

**Mock temporal data:** `data/accidents.geojson` uses `timestamp_offset_hours`; the mock provider converts it to concrete timestamps relative to `now` (tests freeze `now` — see `frozen_now` fixture).

Every request is logged to `backend/logs/requests.jsonl` (JSON lines).

## Frontend architecture

**The UI ↔ backend contract is exactly `{query, boundaries: MultiPolygon | null}`** — mirrored between `frontend/src/types/geo-query.ts` and `backend/app/service/dto.py`. Never change one side without the other. Geography modes (viewport bbox / drawn polygon / rectangle) all collapse into that single MultiPolygon before sending.

**State flow:** `components/AppShell/index.tsx` is the single state owner (query text, geography mode, drawn shape, live map view). It builds the request on Run Query and calls `services/geoQueryService.ts`, which POSTs to `/api/query` (proxied to the backend via the rewrite in `next.config.ts` — no CORS involved).

**Component convention:** every component lives in its own folder under `src/components/` as `index.tsx`. Keep this pattern. (`SettingsPanel/` is the ⚙ modal; it talks to `/api/settings` via `services/settingsService.ts` and mirrors `types/settings.ts` ↔ `settings_router.py`.)

**Map specifics** (`components/MapWorkspace/`):
- Leaflet touches `window` at import time, so `LeafletMap.tsx` is loaded via `next/dynamic` with `ssr: false` from the client component `index.tsx`. Don't import react-leaflet from server components.
- Coordinate order differs: GeoJSON/request objects use `[lng, lat]`; Leaflet uses `[lat, lng]`. Conversions happen inside `LeafletMap.tsx` — keep them there.
- Drawing is implemented directly with map click handlers (no leaflet-draw plugin): rectangle = two corner clicks, polygon = clicks + double-click to finish (duplicate points from the double-click are deduped).

## Gotchas

- `frontend/AGENTS.md` warns that this Next.js version (16.x) may differ from training data — consult `frontend/node_modules/next/dist/docs/` before using Next APIs you're unsure about.
- Geodesic correctness matters later: never do meters math in WGS84 degrees (backend concern, but don't add naive distance logic to the UI either).
- **Python is pinned to exactly 3.8.10** (`requires-python ==3.8.10`): no `match`, no `X | Y` unions, no builtin generics (`list[str]`) in annotations pydantic/FastAPI evaluate — use `typing.Optional/Union/List/Dict` (`Annotated` from `typing_extensions`). The local 3.13 `.venv` is legacy; pip refuses to reinstall the project there — the Docker image is the runtime.
- The image must be built/run as **linux/amd64** — fiona ships no linux-arm64 wheels for py3.8 (fiona is pinned `<1.10`; 1.10 has no py3.8 wheels at all).
- Inside the container, host Postgres is `pghost` (via `--add-host=pghost:host-gateway`) — `host.docker.internal` resolves to an unreachable IPv6, and the URL needs an explicit user (container user is root).
- **Ollama must listen on all interfaces** for the container to reach it: `OLLAMA_HOST=0.0.0.0:11434 ollama serve` (default 127.0.0.1 binding is unreachable from Docker; exposes 11434 on the LAN while running). The LLM client has a degradation ladder for OpenAI-compat servers: JSON mode → plain → system prompt merged into the user turn.
- Layer-selection quality eval: `backend/scripts/eval_select_layers.py` (10 canned Hebrew/English queries incl. an ambiguous one that must clarify). Save failing real queries into `tests/fixtures/` per the MVP guide.
