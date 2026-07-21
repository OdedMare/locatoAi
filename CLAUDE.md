# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

LocatoAI — a Geo-AI query application: users ask geographic questions in natural language (e.g. "Find schools near train stations in Tel Aviv"), scope them to a viewport or drawn polygon/rectangle, and a live LLM agent turns them into a validated geo query plan executed against GIS providers.

**Primary mission:** locate OurForce entities from the Tyche `כוחותינו` layer and determine
what named places, objects, infrastructure, or events are nearby using matching MQS/Cubes
layers as spatial references. This is a priority workflow, not a global restriction:
non-OurForce queries retain the generic subject/reference behavior, and provider roles must
come from catalog metadata rather than hardcoded layer UUIDs.

- `frontend/` — Next.js 16 (App Router) + TypeScript + Leaflet UI, plus a ⚙ settings panel (LLM key/model, PG connection, layers table).
- `backend/` — FastAPI + GeoPandas plan executor + **the FULL agent pipeline, live**: layer selection (call 1) → plan building (call 2) → validate → execute, all via an OpenAI-compatible LLM.

**Where we are:** the MVP works end to end with MQS, Cubes, and Tyche as production GIS providers. Tyche supplies the canonical OurForce observations. MQS is request-scoped: entity layers are never mirrored into backend memory. Every query pushes its boundary to MQS and dense results are split adaptively into geographic quadrants, deduplicated by `entity_id`, and rechecked against the original polygon. Cubes discovers official metadata/parameters, merges them with arbitrary response schemas, and parses WKT POINT locations dynamically. Provider geometry pushdown is always rechecked locally. Every setting has an `AILOCATOR_*` environment default and the Settings UI remains a live-override layer. Secrets are write-only. TLS verification defaults to enabled independently for every provider. Test GIS adapters live under `tests/` and are excluded from the non-root production image. **Next candidates:** MQS server-side count/min/max pushdown, persistent server-side conversation context, client timezone, and SSE streaming.

**MQS bounded loading:** Every query-layer load defaults to the request polygon;
non-proximity reference layers use the exact polygon, and bounded proximity uses only its
metric expansion. MQS responses are locally intersected with that geometry even if the
remote service ignores the POST filter. When `total_entities` exceeds the 10,000-row page,
the provider recursively splits the region into quadrants—even for a physically small but
dense polygon. Splitting stops when a child does not reduce load, recursion is bounded,
cross-tile results are deduplicated, a single layer load is capped at 10,000 distinct
entities, and the final interactive data result across the whole query is capped at
50,000 distinct entities. A plan's `eq`-operator `attribute_filter` steps are pushed down
to MQS as `simple_operators.match` (merged into the same POST body as any geometry
filter) — an optimization only; `attribute_filter` always re-applies client-side, so an
MQS instance that ignores the match body stays correct, just slower. Single-entity detail
is fetched from `GET /MoriaProject/{id}/EntityInfo/{entity_id}` — a distinct route from
`/Entities`, not a sub-path of it; never conflate the two. EntityInfo is best-effort
enrichment: an unavailable or malformed detail response falls back to the entity already
returned by `/Entities` instead of failing the complete layer request with HTTP 502.

**MQS business metadata:** `property_list` accepts object, name/value-array,
camel/Pascal-case, nested-wrapper, and JSON-string variants. Fixed transport fields stay
queryable but set `LayerField.metadata_relevant=false`; metadata/tag generation must use
only real business fields and must fail when none are found. Never reintroduce generic
polygon, triangle, clearance, area, perimeter, source-id, record-id, or timestamp tags.

**Agent loop:** planning has up to three `sample_field` calls and one validation correction. Execution emits per-step counts. Zero rows permit one diagnosis/replan/re-execution. `preserves_constraints` rejects revisions that remove or widen filters, time, geography, distances, counts, targets, `netId` identity, or movement thresholds. Never add an unbounded loop or arbitrary SQL/HTTP tool. `llm_diet_mode` defaults on and dynamically selects compact select/build prompts, compact schemas/tool samples, and a 1,200-token completion cap; the full profile remains available in Settings. Keep both prompt profiles operation-complete and update them together when adding a plan operation.

**Cubes catalog workflow:** the executor supports the legacy one-hour payload and exact
`<field>.match`/`<field>.not` parameters declared by Cubes metadata. A temporal plan range
is pushed to `.match` as `From`/`To`; geography is added through the available temporal
parameter's `Location` and rechecked locally. This behavior is Cubes-only and must not
change MQS's documented `geo_bounding_box`/`geo_polygon` requests. The Layers UI accepts
a bare database name; the backend canonicalizes it to
`cubes://db/<dbname>`. `CubesProvider` reads `GET /cube/v1/{cubeName}` and falls back to
`GET /cube/v1/{cubeName}/parameters`, merges declared fields with sampled response fields,
and gives the official cube name/description, parameter options, and entity samples to
`LayerMetadataGenerator`. Name-only parameter entries are hydrated from
`GET /cube/v1/{cubeName}/parameters/{parameterName}` before required flags, types,
options, or defaults are interpreted. Suffixed parameter names are preserved exactly; a plain name
keeps the legacy plain/`.not` pair. Never hardcode the response field list.
Any non-empty parameter `Value` configured in Cubes metadata is included unchanged in
the request body; this is how required fixed selectors such as `environment=prod` are
satisfied. Configured values remain internal and must not be serialized into LLM prompts.

**Cubes dynamic parameters:** dynamic parameter names are not fixed (`vehicleType`,
`fl:dynamic`, etc.). Discover `Role=dynamic` metadata and names ending in `:dynamic`; when
metadata omits or misclassifies a selector, the catalog lets the user add its exact name
manually. Resolved manual parameters must still be injected even when absent from metadata.
Dynamic selectors are backed by a child autocomplete cube. Their declared `Options` are
unusable placeholders, and valid values must be fetched live via `POST /cube/v1/{cubeName}/autocomplete/
{parameterName}`, which returns `[{"Value": ..., "Name": ...}]`. `LayerParameter.is_dynamic`
marks these; `CubesProvider.fetch_autocomplete_options` calls the route on demand — never
cached, since these cubes can change schema between calls. Resolution happens once at
layer-add time in the catalog UI (`POST /api/layers/autocomplete-parameter`), not per query:
metadata generation is two-phase and MUST NOT fetch cube rows until every dynamic value
and configurable required selector has been resolved; the resolved metadata request then
samples the normal cube route. Required static selectors use declared options or free text.
Preserve the complete parameter name in the autocomplete route, catalog source URL, and
final Cubes request body. The chosen `{parameter_name: value}` map is folded into
`source_url` as `param_<name>=<value>`
query params (parsed back out by `cubes_resolved_parameters`), the same mechanism already
used for `query_mode`. New clients send the map as `cubes_parameters`; the legacy
`cubes_dynamic_parameters` property remains accepted. A required dynamic parameter with
no resolved value fails loudly at fetch time rather than guessing. A declared `polygon`
parameter receives `{"value": [<boundary WKT>]}` and a plain `date` parameter receives
the Cubes `no_time` shape; other cubes retain the existing temporal/`Location` behavior.

**Cubes result cap:** metadata `ResultsLimit` defaults to 10,000 when absent. A bounded
query that hits the cap uses adaptive quadtree subdivision of only saturated tiles and
deduplicates complete observation JSON. Keep recursion bounded and preserve the 100,000
row safety ceiling. Never silently accept a capped unbounded query as complete.

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

**Code-size standard:** one top-level class per Python module. New or touched functions
should stay at 20 lines or fewer and coordinate focused helpers; split parsing, validation,
I/O, trace construction, and result conversion instead of growing orchestration methods.
Small DTO/model modules and trivial protocol declarations are the intended unit of reuse.

**Full architecture explanation lives in `backend/README.md`** — keep it updated when structure changes. Summary:

Tiers under `backend/app/` — dependency direction is service → bl ← dal (DIP: BL contexts own `LayersRepository`/`Provider`/`ProviderRegistry`/`LLMClient`; the DAL implements them; `main.py` is the composition root that wires everything):

- `service/` — routers + DTOs only, no logic. `POST /api/query` (NL entry), `POST /api/execute-plan` (debug: run a hand-written plan), `POST /api/select-layers` (debug: agent call 1 only), `GET/PUT /api/settings` (backs the UI settings panel; secrets masked, responses include live catalog status), `GET /api/models` (live model ids from the configured OpenAI-compatible provider), and `GET/POST /api/layers` (browse/add catalog metadata).
- `bl/plan/` — **GeoQueryPlan is the core contract**: a 16-member discriminated union, including `latest_per_entity` and `movement_direction` for Cubes trajectories. Cubes identity defaults to `netId` and observation time to `eventTime`. Semantic validation enforces earlier references, catalog IDs, complete target filters, required boundaries, final output ordering, and terminal count.
- `bl/executor/` — engine dispatches via an op registry; each op is one self-registering module in `ops/` (OCP: new op = new file, engine untouched).
- `bl/agent/` — focused `select_layers/`, `build_plan/`, and `generate_layer_metadata/` packages. Selection drops hallucinated IDs and sanitizes catalog text; planning receives selected-layer schemas/samples, supports bounded sampling, validates, retries once, and can clarify. Prompts remain files in `prompts/`. `bl/query_orchestrator.py` owns select → plan → execute, zero-result diagnosis, timings, and token usage.
- `dal/` — `catalog/layers_repository.py` owns catalog SQL; provider-specific packages compose one-class-per-file collaborators for source parsing, query building, HTTP/pagination, schema mapping, and dense-result splitting; `llm/openai_client.py` implements the OpenAI-compatible LLM port. Production contains no mock provider.

**Layer catalog is Postgres**, not a file: table `public.layers` in the local `gis` DB (25 Hebrew layers; columns id/name/description/tags/provider/source_url). Plans reference layers by UUID.

**Settings precedence:** `AILOCATOR_*` env vars / `OPENAI_API_KEY` (`app/common/config.py`) are only DEFAULTS feeding `app/common/runtime_settings/`; anything saved via the UI settings panel persists to `backend/runtime-settings.json` (gitignored, mounted into the container) and **overrides env**. Consumers read the store per call, so settings changes need no restart. Postgres host/port/database/user/password can be entered separately and override their corresponding values embedded in `database_url`; blank override fields fall back to the URL, and passwords are write-only in the API. The layers table name is identifier-validated + quoted before entering SQL.

**Locked decisions** (from the MVP guide — don't relitigate): agent emits plans, never SQL; meters math only after reprojecting to EPSG:2039 (`common/geo.py`), never in WGS84 degrees; provider metadata is untrusted input for prompts; clarify is a first-class response, not a confidence score.

**Test temporal data:** `data/accidents.geojson` uses `timestamp_offset_hours`; the test provider converts it relative to frozen `now` values.

Every request is logged to the server console first and then to
`backend/logs/requests.jsonl`. Query logs carry request IDs, live pipeline stage/step
events, layer and plan diagnostics, and result counts without dumping feature bodies. Errors
include method, path, status, exception type/message, and traceback. MQS schema discovery
and plan formatting log dynamic field names and bounded sample counts; frontend failures
also go to the browser console.

## Frontend architecture

**The UI ↔ backend contract is exactly `{query, boundaries: MultiPolygon}`** — mirrored between `frontend/src/types/geo-query.ts` and `backend/app/service/query/request.py`. Never change one side without the other. Geography modes (viewport bbox / drawn polygon / rectangle) all collapse into that required MultiPolygon before sending; viewport is the default.

**State flow:** `components/AppShell/index.tsx` is the single state owner (query text, geography mode, drawn shape, live map view, current request/response, up to eight completed in-memory turns, settings visibility). It builds the request when the composer is submitted and calls `services/geoQueryService.ts`, which POSTs to `/api/query` (proxied to the backend via the rewrite in `next.config.ts` — no CORS involved). A reply following `status="clarify"` includes the immediately preceding request as textual context; this is not persistent server conversation memory. “New geo query” resets conversation and geography state.

**UI layout:** the application UI is Hebrew-first and globally RTL (`<html lang="he" dir="rtl">`). Technical values such as URLs, credentials, provider names, model ids, table names, and JSON stay LTR. The spatial-intelligence workspace uses a dark navigation/history sidebar, bounded conversation surface, live status cues, and bottom composer. Quick-question presets are intentionally absent. `QueryPanel` owns layout only; `AgentTrace`, `ResultsPanel`, and `RequestPreview` render the assistant response. `RequestPreview` can copy the full request/response/plan/trace debug bundle. Geography choices are compact chips above the composer. Light/dark theme state lives in `AppShell`, follows the OS on first visit, persists as `locato-theme` in localStorage, and is applied through `data-theme` on `<html>`. Styling is centralized in `src/styles/globals.css`; icons come from `lucide-react`.

**Catalog UI:** `LayersPanel` browses/searches the PostgreSQL catalog, browses MQS inventory, can generate editable metadata suggestions from sampled entities, creates individual catalog rows, and can bulk-sync MQS. The browser only calls backend catalog endpoints; MQS and PostgreSQL remain server-side. New rows default to `provider="mqs"`.

**Component convention:** feature components normally live in their own folder under `src/components/` as `index.tsx`. MapWorkspace is the deliberate exception: its Leaflet-only helpers (`LeafletMap.tsx`, `MapGeoms.tsx`, `MapLayers.tsx`, `LayerPicker.tsx`, `consts.ts`) are colocated because they form one client-only map feature. (`SettingsPanel/` is the settings modal; it talks to `/api/settings` via `services/settingsService.ts` and mirrors `types/settings.ts` ↔ `settings_router.py`.)

**Map specifics** (`components/MapWorkspace/`):
- Leaflet touches `window` at import time, so `LeafletMap.tsx` is loaded via `next/dynamic` with `ssr: false` from the client component `index.tsx`. Don't import react-leaflet from server components.
- Coordinate order differs: GeoJSON/request objects use `[lng, lat]`; Leaflet uses `[lat, lng]`. Conversions happen inside the map components — keep them there.
- `MapWorkspace` owns the map HUD and top-center coordinate console. It copies the live
  map center as lat/lon, lon/lat, DMS, or WKT; keep it separate from the top-right layer picker.
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
