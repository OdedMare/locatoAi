# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

LocatoAI — a Geo-AI query application: users ask geographic questions in natural language (e.g. "Find schools near train stations in Tel Aviv"), optionally scope them to a map area, and (in future stages) an LLM agent turns them into a validated geo query plan executed against GIS providers.

- `frontend/` — Next.js 16 (App Router) + TypeScript + Leaflet UI.
- `backend/` — FastAPI + GeoPandas plan executor (Day 1 of the MVP guide: plan-in → GeoJSON-out). The Claude agent (Day 2) is stubbed in `app/bl/agent/`; `POST /api/query` returns a clarify message until it lands.

## Commands

```bash
# backend (requires local Postgres 'gis' DB — see below)
# Python runtime is EXACTLY 3.8.10 (requires-python pin). No local 3.8.10
# exists on ARM macs — use the Docker image:
cd backend
docker build -t ailocator-backend:py3.8.10 .                      # build (rebuild after dep changes)
docker run --rm -p 8000:8000 ailocator-backend:py3.8.10           # serve API (DB via host.docker.internal)
docker run --rm ailocator-backend:py3.8.10 python -m pytest -q    # run tests
docker run --rm ailocator-backend:py3.8.10 python -m pytest tests/test_executor.py::test_near_uses_meters_not_degrees  # single test
# Code changes require rebuild (source is COPYed, not mounted); for a quick
# iteration loop mount it: docker run --rm -p 8000:8000 -v "$PWD/app:/srv/backend/app" ailocator-backend:py3.8.10

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

- `service/` — routers + DTOs only, no logic. `POST /api/query` (NL entry, agent-stubbed), `POST /api/execute-plan` (debug: run a hand-written plan — this is the real, tested path).
- `bl/plan/` — **GeoQueryPlan is the core contract**: discriminated union of 6 step types (`load`, `within_geometry`, `attribute_filter`, `near`, `directional`, `temporal_filter`), semantic validation in `validators.py` (refs must point to earlier steps, so list order is execution order).
- `bl/executor/` — engine dispatches via an op registry; each op is one self-registering module in `ops/` (OCP: new op = new file, engine untouched).
- `bl/agent/` — Day 2 stubs. `bl/query_orchestrator.py` owns the select → plan → validate → execute flow and the retry/clarify policy.
- `dal/` — `layers_repository.py` (the only SQL) + `providers/arcgis_mock.py` (serves `data/*.geojson`, file picked by the source_url's last path segment).

**Layer catalog is Postgres**, not a file: table `public.layers` in the local `gis` DB (25 Hebrew layers; columns id/name/description/tags/provider/source_url). Plans reference layers by UUID. Config via `AILOCATOR_*` env vars (`app/common/config.py`); default DB URL `postgresql://localhost:5432/gis`.

**Locked decisions** (from the MVP guide — don't relitigate): agent emits plans, never SQL; meters math only after reprojecting to EPSG:2039 (`common/geo.py`), never in WGS84 degrees; provider metadata is untrusted input for prompts; clarify is a first-class response, not a confidence score.

**Mock temporal data:** `data/accidents.geojson` uses `timestamp_offset_hours`; the mock provider converts it to concrete timestamps relative to `now` (tests freeze `now` — see `frozen_now` fixture).

Every request is logged to `backend/logs/requests.jsonl` (JSON lines).

## Frontend architecture

**The UI ↔ backend contract is exactly `{query, boundaries: MultiPolygon | null}`** — mirrored between `frontend/src/types/geo-query.ts` and `backend/app/service/dto.py`. Never change one side without the other. Geography modes (viewport bbox / drawn polygon / rectangle) all collapse into that single MultiPolygon before sending.

**State flow:** `components/AppShell/index.tsx` is the single state owner (query text, geography mode, drawn shape, live map view). It builds the request on Run Query and calls `services/geoQueryService.ts`, which POSTs to `/api/query` (proxied to the backend via the rewrite in `next.config.ts` — no CORS involved).

**Component convention:** every component lives in its own folder under `src/components/` as `index.tsx`. Keep this pattern.

**Map specifics** (`components/MapWorkspace/`):
- Leaflet touches `window` at import time, so `LeafletMap.tsx` is loaded via `next/dynamic` with `ssr: false` from the client component `index.tsx`. Don't import react-leaflet from server components.
- Coordinate order differs: GeoJSON/request objects use `[lng, lat]`; Leaflet uses `[lat, lng]`. Conversions happen inside `LeafletMap.tsx` — keep them there.
- Drawing is implemented directly with map click handlers (no leaflet-draw plugin): rectangle = two corner clicks, polygon = clicks + double-click to finish (duplicate points from the double-click are deduped).

## Gotchas

- `frontend/AGENTS.md` warns that this Next.js version (16.x) may differ from training data — consult `frontend/node_modules/next/dist/docs/` before using Next APIs you're unsure about.
- Geodesic correctness matters later: never do meters math in WGS84 degrees (backend concern, but don't add naive distance logic to the UI either).
