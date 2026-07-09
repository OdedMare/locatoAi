# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

LocatoAI — a Geo-AI query application: users ask geographic questions in natural language (e.g. "Find schools near train stations in Tel Aviv"), optionally scope them to a map area, and (in future stages) an LLM agent turns them into a validated geo query plan executed against GIS providers.

- `frontend/` — Next.js 16 (App Router) + TypeScript + Leaflet UI. **Stage 1 (UI-only) is built.**
- `backend/` — empty placeholder. Planned: FastAPI + Claude agent + provider router (see the AiLocator MVP guide when it lands in the repo). No AI, SQL, or real GIS execution exists yet.

## Commands

All frontend work happens in `frontend/`:

```bash
cd frontend
npm run dev      # dev server on http://localhost:3000
npm run build    # production build (also typechecks)
npm run lint     # ESLint
npx tsc --noEmit # typecheck only
```

There are no tests yet.

## Frontend architecture

**The UI ↔ backend contract lives in `frontend/src/types/geo-query.ts`** (`GeoQueryRequest`: `queryText`, `geography.{mode, geometry, bbox}`, `uiContext.{mapCenter, mapZoom}`). The future agent/backend consumes exactly this shape — do not change it casually.

**State flow:** `components/AppShell/index.tsx` is the single state owner (query text, geography mode, drawn shape, live map view). It builds the request object on Run Query and calls `services/mockGeoQueryService.ts` — the designated swap point for the real `POST /api/geo-query` call (integration comments are in that file).

**Component convention:** every component lives in its own folder under `src/components/` as `index.tsx`. Keep this pattern.

**Map specifics** (`components/MapWorkspace/`):
- Leaflet touches `window` at import time, so `LeafletMap.tsx` is loaded via `next/dynamic` with `ssr: false` from the client component `index.tsx`. Don't import react-leaflet from server components.
- Coordinate order differs: GeoJSON/request objects use `[lng, lat]`; Leaflet uses `[lat, lng]`. Conversions happen inside `LeafletMap.tsx` — keep them there.
- Drawing is implemented directly with map click handlers (no leaflet-draw plugin): rectangle = two corner clicks, polygon = clicks + double-click to finish (duplicate points from the double-click are deduped).

## Gotchas

- `frontend/AGENTS.md` warns that this Next.js version (16.x) may differ from training data — consult `frontend/node_modules/next/dist/docs/` before using Next APIs you're unsure about.
- Geodesic correctness matters later: never do meters math in WGS84 degrees (backend concern, but don't add naive distance logic to the UI either).
