# AiLocator Backend

FastAPI service that turns **natural-language geographic questions** (Hebrew/English) into
validated **Geo Query Plans** executed against GIS data with GeoPandas.

```
"תמצא את בית הקולנוע הכי צפוני"
        │
        ▼
POST /api/query {query, boundaries: MultiPolygon}
        │
        ▼
┌─ QueryOrchestrator ────────────────────────────────────────────┐
│  1. select layers   (LLM call 1 — LIVE)                        │
│  2. build plan      (LLM call 2 — LIVE)                        │
│  3. validate plan   (retry once with the error, then clarify)  │
│  4. execute plan    (GeoPandas ops, EPSG:2039 for meters)      │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
{status, features, scalar_result, plan, selected_layers, pipeline_trace, timing_ms}
```

The model never writes SQL and never invents data sources: it chooses from a
**Postgres layer catalog** and emits a **plan** — a small, validated JSON program
over 16 spatial, filtering, movement, and aggregation operations.

---

## Architecture: N-tier + SOLID

Dependency direction: **service → bl ← dal**. The BL owns its interfaces
([`bl/ports/`](app/bl/ports/)); the DAL implements them; only
[`main.py`](app/main.py) (composition root) knows every tier.

```
app/
├── main.py                  # composition root: wiring + error mapping, nothing else
│
├── service/                 # ── HTTP tier: routers + DTOs, zero logic ──
│   ├── dto/                 # query/plan request and response models
│   ├── *_dto/               # router-specific settings/catalog/agent DTOs
│   ├── query_router.py      # POST /api/query           (NL entry point)
│   ├── plan_router.py       # POST /api/execute-plan    (debug: run a raw plan)
│   ├── agent_router.py      # POST /api/select-layers   (debug: LLM call 1 only)
│   ├── catalog_router.py    # GET/POST /api/layers + POST /api/layers/sync-mqs
│   ├── settings_router.py   # GET/PUT /api/settings     (backs the UI ⚙ panel)
│   ├── feedback_router.py   # POST /api/feedback        (👍/👎 → PostgreSQL)
│   └── deps.py              # FastAPI dependency accessors (app.state)
│
├── bl/                      # ── Business logic tier ──
│   ├── ports/               # one BL-owned protocol/model per focused module
│   ├── query_orchestrator.py# the select → plan → validate → execute flow + retry policy
│   ├── agent/
│   │   ├── select_layers/   # call 1: catalog → prompt → layer ids
│   │   ├── build_plan/      # call 2: schemas → plan, tools, constraint preservation
│   │   ├── generate_layer_metadata/ # provider business fields → editable metadata
│   │   └── prompts/         # prompts are FILES; tuning ≠ code change
│   ├── plan/
│   │   ├── models/          # one Pydantic model per plan step + discriminated union
│   │   └── validators.py    # semantic checks with agent-readable error messages
│   ├── executor/
│   │   ├── engine.py        # runs steps in order, dispatches via the op registry
│   │   └── ops/             # ONE module per op, self-registering (@register_op)
│   └── catalog/
│       ├── catalog_service.py # layer lookup + schema cache (TTL; stale beats failed)
│       └── mqs_sync.py      # MQS layer inventory → catalog upserts (tags preserved)
│
├── dal/                     # ── Data access tier (implements bl.ports) ──
│   ├── postgres.py          # shared live-settings PostgreSQL connection factory
│   ├── layers_repository.py # configurable PostgreSQL catalog table
│   ├── feedback_repository.py # configurable PostgreSQL feedback table
│   ├── providers/
│   │   ├── mqs.py           # MQS REST adapter + property_list enrichment
│   │   ├── cubes.py         # generic Cubes time-varying POINT adapter
│   │   └── registry.py      # provider name → adapter instance
│   └── llm/
│       └── openai_client.py # OpenAI-compatible JSON-mode client (Ollama/Gemma today)
│
└── common/                  # ── Cross-cutting, no business rules ──
    ├── config.py            # env defaults (AILOCATOR_*, OPENAI_API_KEY)
    ├── runtime_settings/    # model, normalizers, persisted live-override store
    ├── errors/              # focused domain exceptions (mapped in main.py)
    ├── geo.py               # CRS helpers — ALL meters math goes through here
    └── logging.py           # structured JSON file + server-console logging
```

The service tier exposes these routes:

| Method and path | Stage / purpose |
|---|---|
| `GET /health` | Process health check; outside the `/api` proxy family. |
| `POST /api/query` | Full natural-language select → plan → validate → execute pipeline. |
| `POST /api/execute-plan` | Validate and execute a supplied plan without either LLM call. |
| `POST /api/select-layers` | Run only agent call one for debugging/evaluation. |
| `GET /api/layers` | Return local catalog metadata. |
| `POST /api/layers` | Create one catalog record. |
| `POST /api/layers/generate-metadata` | Suggest editable description/tags from up to 10 random source entities. |
| `GET /api/layers/mqs` | Browse remote MQS inventory without persisting it. |
| `POST /api/layers/sync-mqs` | Upsert remote MQS inventory into PostgreSQL. |
| `GET /api/mqs-mirror/status` | Report per-layer mirror count, sync state, lag and freshness. |
| `GET /api/settings` | Read masked runtime settings and live catalog status. |
| `PUT /api/settings` | Validate and persist runtime setting overrides. |
| `GET /api/models` | List models with saved LLM settings. |
| `POST /api/models` | Probe models using unsaved URL/key overrides. |
| `POST /api/feedback` | Persist a thumbs verdict and selection context. |

`main.py` creates the settings store, repositories, provider registry, MQS
provider, catalog, executor, LLM client, both agent stages, and orchestrator.
These long-lived objects are attached to `app.state`; routers retrieve them
directly or through `service/deps.py`.

**How SOLID maps onto it**

| Principle | Where it lives |
|---|---|
| SRP | routers translate HTTP only; each executor op is one module; DAL repositories own SQL |
| OCP | new op = new file in `executor/ops/` (engine untouched); new provider = one `register()` call |
| LSP/ISP | `Provider` is three methods (`describe_schema`, `fetch_features`, `sample_field_values`) — any adapter drops in |
| DIP | BL imports nothing from DAL; it depends on `bl/ports/` Protocols, wired in `main.py` |

---

## The core contract: GeoQueryPlan

Plans are DAGs of steps chained by `id`/`input`. Validators guarantee every
`input` references an **earlier** step, so list order is execution order.

```json
{
  "explanation": "בתי הספר בתל אביב במרחק 300 מ' מכיכר",
  "steps": [
    {"id": "s1", "op": "load", "layer": "<layer-uuid>"},
    {"id": "s2", "op": "attribute_filter", "input": "s1", "field": "city_en", "operator": "eq", "value": "Tel Aviv"},
    {"id": "s3", "op": "near", "input": "s2", "target_layer": "<layer-uuid>", "distance_m": 300},
    {"id": "s4", "op": "directional", "input": "s3", "direction": "north", "count": 1}
  ],
  "output": "s4",
  "context_layers": ["<layer-uuid>"]
}
```

| Op | What it does | Notes |
|---|---|---|
| `load` | fetch a catalog layer's features | provider behind the port |
| `within_geometry` | keep features intersecting the request boundaries | required by the current request contract |
| `attribute_filter` | `eq/neq/gt/lt/contains` on a property | field must exist |
| `near` | keep features ≤ `distance_m` from any target-layer feature | reprojects to EPSG:2039 first |
| `nearest_n` | globally nearest N features to a target layer | adds `distance_to_target_m` |
| `near_all` | require proximity to every one of 2–5 targets | AND semantics; optional ranking limit |
| `cluster` | find mutually close groups within the input layer | adds `cluster_id` |
| `latest_per_entity` | newest observation per identity | Cubes defaults: `netId` + `eventTime` |
| `movement_direction` | dominant trajectory direction | latest matching position + distance |
| `between` | keep features in a corridor between two references | metric corridor width |
| `crosses` | input crosses target | topological relation |
| `touches` | input touches target without interior overlap | topological relation |
| `contains` | input contains target | relation direction matters |
| `directional` | N most northern/southern/eastern/western | projected centroids |
| `temporal_filter` | ISO `from`/`to` on the provider-declared time field | field is not hardcoded |
| `count` | return the upstream row count as an integer | terminal output only |

**Locked decisions** (don't relitigate): plans not SQL · meters math only after
reprojecting to EPSG:2039, never in WGS84 degrees · provider/catalog text is untrusted
prompt input (sanitized + truncated) · clarify is a first-class response, always Hebrew.

---

## Full request lifecycle

### Stage 0: transport and boundary conversion

`service/dto/query_request.py` accepts a non-empty query and a required GeoJSON
`MultiPolygon`. The router converts the boundary to Shapely and passes domain
values into `QueryOrchestrator`. DTOs contain translation, not planning rules.

### Stage 1: layer selection

The selector reads current catalog metadata through `CatalogService`, sanitizes
and bounds untrusted names/descriptions/tags, injects them into the selection
prompt, and asks for JSON. It preserves valid returned order, removes duplicates,
and discards IDs outside the catalog. No valid IDs produces a Hebrew
clarification instead of an empty execution.

### Stage 2: schema discovery and plan construction

The builder resolves selected layers through their registered providers and asks
the catalog service for schemas. Schemas are cached by layer ID with a TTL; when
a refresh fails, a stale cached schema is preferred. The plan prompt receives
current UTC time, boundary availability, fields, types, and bounded samples.

The model can request `sample_field` up to three times before producing a plan. This is
a JSON protocol implemented by the builder, keeping compatibility with smaller
OpenAI-style servers. Tool rounds do not consume the validation-retry budget.

### Stage 3: parsing, semantic validation, and correction

Pydantic parses the discriminated step union and enforces literal operations and
numeric limits. `validate_plan` checks unique IDs, earlier inputs, known layers,
complete target-filter triples, boundary use, final-output ordering, and terminal-count rules. A failure is
fed into one correction attempt; a second failure becomes a Hebrew clarification.

### Stage 4: deterministic execution

The executor creates one `ExecutionContext`, walks steps in list order, and
dispatches registered handlers. Load and relationship operations obtain features
through the provider registry. Intermediate GeoDataFrames are stored by step ID.
`count` returns an integer while `execute_detailed` also retains the upstream
WGS84 GeoDataFrame so the HTTP response can show and map what was counted.

### Stage 5: response, observability, and feedback

`QueryResponse.from_outcome` is the domain-to-HTTP translation. It serializes
GeoDataFrames through `__geo_interface__`, preserving computed fields such as
`distance_to_target_m`. Responses carry the agent trace, stage timings, token
usage, tool calls, and `pipeline_trace`: safe stage/step metadata with durations,
counts, parameters, and statuses (not private model chain-of-thought). Structured
request events are written both to JSON lines and the server console. Domain and
unexpected exceptions log method, path, status, type, message, and traceback; the UI
also writes failed network/API operations to the browser console. User votes go to the
configured PostgreSQL feedback table.

### Bounded agent loop

The planner can sample fields up to three times and correct one invalid plan.
Execution exposes deterministic per-step row counts. Zero rows permit exactly one
tool-assisted diagnosis, revised plan, and re-execution. `preserves_constraints`
rejects revisions that remove or widen time, distance, geography, count, target,
attribute, identity, or movement constraints. The agent has no SQL, arbitrary HTTP,
or unbounded-loop capability.

## The agent

**Call 1 — layer selection (live).** The catalog (25+ Hebrew layers from Postgres:
name/description/tags) goes into [`prompts/select_layers.md`](app/bl/agent/prompts/select_layers.md);
the model reasons first (short Hebrew `reasoning`, shown in the UI), then returns layer ids.
Hallucinated ids are dropped; no match → short Hebrew clarify question.

**Call 2 — plan building (live).** Query + selected layers' schemas (field names/types +
sample values, so filters match the data's language) → GeoQueryPlan JSON → semantic
validation → on failure retry once with the error appended → Hebrew clarify fallback.
Prompt: [`prompts/build_plan.md`](app/bl/agent/prompts/build_plan.md). The orchestrator
returns per-stage timings (`select`/`plan`/`execute`) and summed token usage.

**sample_field tool.** Before committing to a plan, the model may answer
`{"tool": "sample_field", "layer_id": ..., "field": ...}` to receive up to 20 distinct
values of that field (JSON-protocol tool — the client is JSON-mode-only). Max 3 rounds
per query, separate from the validation retry; rounds are reported as `tool_calls` in
the response and listed in the UI agent panel. Backed by `Provider.sample_field_values`
(mock: distinct GeoJSON values; MQS: searchable `property_list` values from entity details).

**Model:** Gemma 4 31B via Ollama cloud (`gemma4:31b-cloud`), configured in the UI ⚙ panel.
The [LLM client](app/dal/llm/openai_client.py) is OpenAI-compatible and key-optional when a
`base_url` is set, with a degradation ladder: JSON mode → plain → system-merged-into-user.

**Quality loop:**
- `scripts/eval_select_layers.py` — SCORED eval (20 Hebrew/English cases with expected
  layer sets, incl. typos/slang/must-clarify; exit 1 on regression). Run after every
  prompt/model change. Add every real-world miss as a case.
- UI 👍/👎 → `POST /api/feedback` → configurable PostgreSQL feedback table.
- `scripts/enrich_layer_tags.py` — LLM-generated bilingual alias tags using catalog
  metadata plus MQS `property_list` field names/samples (dry-run by default;
  `--apply` writes; previous tags in `scripts/tags_backup.txt`).

---

## Providers

The catalog's `provider` column routes each layer to a registered adapter
([`registry.py`](app/dal/providers/registry.py), wired in `main.py`). **Production
registers `mqs` and `cubes`** — `arcgis` is not a real provider anymore.

- **`mqs`** — [`mqs.py`](app/dal/providers/mqs.py): the MQS (Moria Query Service)
  REST API. Catalog rows store `source_url = "mqs://layer/{layerId}"` (base-URL-
  independent; the live base URL is the `mqs_base_url` setting, read per call —
  unset means the provider errors with a clear message → HTTP 502). A background
  `MqsMirrorWorker` scans full-data pages in chunks and keeps current entities in compressed
  process memory with an immutable Shapely STRtree per completed layer snapshot. Refresh
  prefers `POST /Data/MoriaProject/{id}/Entities` with `result_type=data`, `geo_type=wkt`,
  and `IS_DELETED=false`; 404/405 falls back to the legacy list endpoint.
  Full-data rows that include `property_list` require no detail request. On legacy fallback,
  `history_id` equality avoids unchanged details and changed details use a bounded pool.
  Atomic per-layer snapshots isolate concurrent activity. Runtime reads always use the
  latest completed snapshot while the next one is built. Snapshot age is still measured
  against the configured 30-second target, but stale data never triggers a heavy live-MQS
  fallback; a layer without its first snapshot fails fast. When the mirror is disabled,
  live fetching pages through `GET /MoriaProject/{id}/Entities` (page 10,000, hard cap 50k)
  and follows `GET /MoriaProject/{id}/Entities/{entity_id}` to flatten each entity's
  `property_list` into normal feature columns. Those columns drive schema discovery,
  value sampling, metadata/tag generation, attribute filters, displayed results, and
  every spatial operation. Property parsing accepts objects, name/value arrays,
  camel/Pascal-case names, nested wrappers, and JSON-encoded strings. Fixed transport
  fields (`triangle`, `clearence_level`, `source_id`, `date`, `area`, `perimeter`) remain
  queryable but have `metadata_relevant=false`; description/tag generation receives only
  business `property_list` fields and fails if none are found rather than producing
  polygon/clearance tags. Schema and planner logs expose discovered field names and
  bounded sample counts for diagnosis. Viewport/polygon filters are pushed down with
  POST for every query layer and are always rechecked locally before GeoDataFrame
  construction, even if MQS ignores the filter. Bounded
  `near`/`near_all` target loads use the request geometry expanded in a local metric CRS,
  avoiding a complete target-layer load without excluding any possible match.
  The STRtree returns exact polygon candidates, geometry is parsed once per stored entity,
  and the WKT copy is removed from the compressed payload. Mirror status also reports the
  latest candidate/result counts and per-layer query count.

  The entity mirror performs no SQL or filesystem writes and creates no tables. It is
  rebuilt after each backend restart. Layer synchronization defaults to sequential
  operation to avoid loading two large changed batches simultaneously; completed layers
  remain concurrently queryable.
  The `AILOCATOR_MQS_MIRROR_*` and `AILOCATOR_MQS_DETAIL_CONCURRENCY` settings are listed
  in `.env.example`. Replication diff can remove the remaining full page scan once its exact
  cursor/header contract is available; the current full-data endpoint already removes the
  normal per-entity detail fan-out.

- **`cubes`** — [`cubes.py`](app/dal/providers/cubes.py): time-varying entity
  locations such as buses. Rows use `source_url="cubes://db/<dbname>"`. The provider
  reads metadata with `GET /cube/v1/<dbname>` and falls back to
  `GET /cube/v1/<dbname>/parameters` when parameter definitions are not embedded.
  It posts metadata-driven temporal payloads to `/cube/v1/<dbname>`, sends the write-only
  Authorization token, and converts WKT POINT geometry to WGS84. Declared fields are
  merged with every non-geometry JSON key discovered dynamically; types, samples, and
  the temporal field are inferred and cached. Exact `<name>.match` and `<name>.not`
  names are preserved. `.match` receives the plan's ISO `From`/`To` range, `.not`
  receives the relative time-back shape, and an unsuffixed parameter keeps the legacy
  plain/`.not` pair. User geometry is sent through the available temporal parameter's
  `Location` and is rechecked locally before applying a result limit.
  Moving-entity plans use `netId` as identity and `eventTime` as time. The
  `latest_per_entity` and `movement_direction` operations prevent repeated observations
  from being mistaken for multiple vehicles and support trajectory questions.
  `ResultsLimit` controls truncation detection (default 10,000). When a bounded request
  reaches it, the provider adaptively splits only saturated spatial tiles, recursively
  fetches them, and deduplicates complete JSON observations. Depth and a 100,000-row
  safety ceiling prevent runaway fan-out; an unbounded capped request fails loudly.
  The generic metadata endpoint accepts a bare database name, normalizes it to
  `cubes://db/<dbname>`, fetches a bounded sample, and feeds the cube's official
  name/description, fields, request parameters/options, and entity samples to editable
  description/tag generation.

**Catalog sync:** `POST /api/layers/sync-mqs` (UI: button in the layers panel) pulls
`GET /MoriaProject/Layers` and upserts rows keyed on `(provider, source_url)` —
re-syncs update name/description in place and **preserve tags** (rerun
Test-only GIS adapters live under `tests/`; no mock provider is shipped in `app/`
or copied into the production container.

---

## Settings

Two layers, one store ([`runtime_settings_store.py`](app/common/runtime_settings/runtime_settings_store.py)):

1. **Env defaults** — `AILOCATOR_*` vars / `OPENAI_API_KEY` ([`config.py`](app/common/config.py)).
2. **UI overrides** — whatever is saved in the ⚙ panel persists to `runtime-settings.json`
   (gitignored, mounted into the container) and **wins over env**.

Consumers read the store **per call** — settings changes need no restart.
Both layers and feedback table names are identifier-validated and quoted before
entering SQL. The database URL accepts PostgreSQL URLs and normalizes pasted JDBC
PostgreSQL URLs. Optional user, password, host, port, and database fields override
the matching URL parts.

The catalog and feedback repositories share the same live connection settings.
The feedback repository creates its configured table on first use and stores the
query, verdict, selected-layer names, reasoning, clarification, and timestamp.
The PostgreSQL role therefore needs catalog access and permission to create or
write that feedback table.

Secrets have write-only API semantics: empty key/password fields keep the saved
value, GET responses expose only presence or masked hints, and the full values
remain in the backend runtime settings file.

Every deployable setting has an environment default; see [`.env.example`](.env.example).
UI values remain live overrides. MQS and Cubes verify TLS certificates by default.

---

## Running

Python is pinned to **exactly 3.8.10**; the Docker image is the runtime
(no arm64 wheels exist for the py3.8 geo stack — the image is linux/amd64):

```bash
docker build --platform linux/amd64 -t ailocator-backend:py3.8.10 .

docker run -d --name ailocator-backend --platform linux/amd64 -p 8000:8000 \
  --add-host=pghost:host-gateway \
  -e AILOCATOR_DATABASE_URL=postgresql://$(whoami)@pghost:5432/gis \
  -v "$PWD/runtime-settings.json:/srv/backend/runtime-settings.json" \
  ailocator-backend:py3.8.10

docker run --rm --platform linux/amd64 ailocator-backend:py3.8.10 python -m pytest -q
docker exec ailocator-backend python scripts/eval_select_layers.py
```

Requires: local Postgres `gis` DB with the `public.layers` catalog, and Ollama listening
on all interfaces (`OLLAMA_HOST=0.0.0.0:11434 ollama serve`) signed in for cloud models.
Inside the container the host is `pghost` (host-gateway) — `host.docker.internal` breaks on IPv6.

**Python 3.8 constraints:** no `match`, no `X | Y` unions, no builtin generics in
annotations that pydantic/FastAPI evaluate — use `typing.Optional/Union/List/Dict`.

## Tests

`tests/` runs without Postgres or an LLM: fakes implement the `bl/ports/` protocols
(this is DIP paying rent). Mock data lives in `data/*.geojson`; accident timestamps are
generated relative to `now`, which tests freeze (`frozen_now` fixture). Golden plans:
`tests/fixtures/plans/`.

The production image installs runtime dependencies only, copies only `app/`, and
runs as an unprivileged `app` user. Tests, scripts, and fixture data are excluded.

## Roadmap

1. Multi-turn clarify (conversation state), `client_now`/timezone in the request.
2. SSE status streaming; real ArcGIS provider; PostGIS.
3. End-to-end scored eval for plan building (selection already has one).
