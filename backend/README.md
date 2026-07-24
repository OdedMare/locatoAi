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

Dependency direction: **service → bl ← dal**. The BL owns interfaces beside the
contexts that consume them; the DAL implements them; only
[`main.py`](app/main.py) / [`application_state_wiring.py`](app/application_state_wiring.py)
(composition root) know every tier.

```
app/
├── main.py                  # composition root: app factory + error mapping
├── application_state_wiring.py # composition root: builds the dependency graph onto app.state
│
├── service/                 # ── HTTP tier: one package per API context ──
│   ├── query/               # POST /api/query + request/response DTOs and event sink
│   ├── plan/                # POST /api/execute-plan + request DTO
│   ├── agent/               # POST /api/select-layers + DTOs
│   ├── agent_config/        # GET/PUT prompts + skills; POST custom skill
│   ├── catalog/             # Layer CRUD, MQS sync/browse, Tyche activation + DTOs
│   ├── settings/            # GET/PUT /api/settings + DTOs
│   ├── models/              # GET/POST /api/models + DTOs
│   ├── feedback/            # POST /api/feedback + request DTO
│   ├── errors/              # domain-error → HTTP handlers
│   ├── health/              # GET /health handler
│   ├── shared/              # shared GeoJSON translation models
│   └── dependencies.py      # FastAPI dependency accessors (app.state)
│
├── bl/                      # ── Business logic tier ──
│   ├── query_orchestrator/
│   │   └── query_orchestrator.py # the select → plan → validate → execute flow + retry policy
│   ├── agent/
│   │   ├── llm_client.py    # BL-owned LLM protocol
│   │   ├── select_layers/   # call 1: catalog → prompt → layer ids
│   │   ├── build_plan/      # call 2: schemas + geo skills → plan and validation loop
│   │   ├── generate_layer_metadata/ # provider business fields → editable metadata
│   │   ├── prompts/         # prompt shells and stage policy
│   │   └── skills/          # one model-facing reference per plan operation
│   ├── plan/
│   │   ├── models/          # one Pydantic model per plan step + discriminated union
│   │   └── validators.py    # semantic checks with agent-readable error messages
│   ├── executor/
│   │   ├── engine/          # runs steps in order, dispatches via the op registry
│   │   └── ops/             # ONE module per op, self-registering (@register_op)
│   ├── providers/           # BL-owned provider and registry protocols
│   └── catalog/
│       ├── models/          # layer metadata/schema/parameter models
│       ├── layers_repository.py # BL-owned catalog repository protocol
│       ├── catalog_service.py   # layer lookup + schema cache (TTL; stale beats failed)
│       └── mqs_sync/            # MQS layer inventory → catalog upserts (tags preserved)
│
├── dal/                     # ── Data access tier (implements BL interfaces) ──
│   ├── agent_content/       # file defaults + persisted live UI overrides
│   ├── database/postgres.py # shared live-settings PostgreSQL connection factory
│   ├── catalog/             # configurable PostgreSQL catalog repository
│   ├── feedback/            # configurable PostgreSQL feedback repository
│   ├── providers/
│   │   ├── mqs/             # MQS REST adapter + collaborators
│   │   ├── cubes/           # generic Cubes adapter + collaborators
│   │   ├── tyche/           # Tyche adapter + collaborators
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
| `PUT /api/layers/{id}` | Edit layer name, description, and tags without changing its provider/source. |
| `POST /api/layers/generate-metadata` | Suggest editable description/tags from up to 10 random source entities; also reports any Cubes dynamic (autocomplete-backed) parameter names. |
| `POST /api/layers/autocomplete-parameter` | Fetch live values for a Cubes dynamic parameter (never cached — the source cube can change schema). |
| `POST /api/layers/activate-tyche` | Probe Tyche and idempotently activate the Our Forces layer. |
| `GET /api/layers/mqs` | Browse remote MQS inventory without persisting it. |
| `POST /api/layers/sync-mqs` | Upsert remote MQS inventory into PostgreSQL. |
| `GET /api/settings` | Read masked runtime settings and live catalog status. |
| `PUT /api/settings` | Validate and persist runtime setting overrides. |
| `GET /api/models` | List models with saved LLM settings. |
| `POST /api/models` | Probe models using unsaved URL/key overrides. |
| `POST /api/feedback` | Persist a thumbs verdict and selection context. |

`main.py` creates the settings store, repositories, provider registry, MQS,
Cubes and Tyche providers, catalog, executor, LLM client, both agent stages,
and orchestrator.
These long-lived objects are attached to `app.state`; routers retrieve them
directly or through `service/dependencies.py`.

**How SOLID maps onto it**

| Principle | Where it lives |
|---|---|
| SRP | routers translate HTTP only; each executor op is one module; DAL repositories own SQL |
| OCP | new op = new file in `executor/ops/` (engine untouched); new provider = one `register()` call |
| LSP/ISP | `Provider` is three methods (`describe_schema`, `fetch_features`, `sample_field_values`) — any adapter drops in |
| DIP | BL imports nothing from DAL; context-owned BL Protocols are wired in `main.py` |

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
| `movement_direction` | movement in any or a dominant compass direction | latest matching position + path distance/displacement |
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

`service/query/request.py` accepts a non-empty query and a required GeoJSON
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
request events are written to the server console first and then to JSON lines. Query
logging includes a request ID, boundary summary, live stage transitions, selected and
dropped layer IDs, raw plan-validation diagnostics, per-step parameters/counts, and the
complete final plan/trace. Result feature bodies are intentionally summarized by count.
Domain and
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
Prompt: [`prompts/build_plan.md`](app/bl/agent/prompts/build_plan.md), composed with the
shared [`plan-geo-queries`](app/bl/agent/skills/plan-geo-queries/SKILL.md) operation
catalog. The orchestrator returns per-stage timings (`select`/`plan`/`execute`) and
summed token usage.

**sample_field tool.** Before committing to a plan, the model may answer
`{"tool": "sample_field", "layer_id": ..., "field": ...}` to receive up to 20 distinct
values of that field (JSON-protocol tool — the client is JSON-mode-only). Max 3 rounds
per query, separate from the validation retry; rounds are reported as `tool_calls` in
the response and listed in the UI agent panel. Backed by `Provider.sample_field_values`
(mock: distinct GeoJSON values; MQS: searchable `property_list` values from entity details).

**Diet mode.** `llm_diet_mode` defaults to true and is live-editable through
`GET/PUT /api/settings`. It switches both query-agent stages to compact prompt files,
compacts catalog descriptions and schema samples, limits sampled tool values, and sends
`max_tokens=1200` to the OpenAI-compatible completion endpoint. All plan operations,
validation retries, sampling rounds, and zero-result replanning remain available. The
fixed build prompt remains roughly half the full profile by rendering only each skill's
use/avoid rules and JSON shape; actual size varies with the catalog and selected schemas.
Set `AILOCATOR_LLM_DIET_MODE=false` or clear the UI toggle to run the full prompts for
quality comparison.

**Agent Studio.** `GET /api/agent-config` exposes the five active prompt templates and
the operation-skill catalog. `PUT /api/agent-config/{kind}/{id}` saves an override, and
`POST /api/agent-config/skills` creates a new planner instruction skill. Overrides and
custom skills persist in `runtime-settings.json`; the selector, planner, and metadata
generator read them on every call, so the next agent request uses the edit without a
backend restart. Required prompt placeholders are validated before saving. These skills
compose existing typed plan operations; adding a new executable operation still requires
its model, validator, executor, trace, and tests.

**Model:** Gemma 4 31B via Ollama cloud (`gemma4:31b-cloud`), configured in the UI ⚙ panel.
The [LLM client](app/dal/llm/openai_client.py) is OpenAI-compatible and key-optional when a
`base_url` is set, with a degradation ladder: JSON mode → plain → system-merged-into-user.

**Quality loop:**
- `scripts/eval_select_layers.py` — SCORED eval (Hebrew/English cases with expected
  layer sets, incl. typos/slang/must-clarify; exit 1 on regression). Run after every
  prompt/model change. Add every real-world miss as a case.
- `scripts/eval_build_plan.py` — SCORED live planner eval with fixed real catalog layers,
  covering proximity choices, clusters, static vs moving direction, count vs limit,
  named references, boundaries, typos, clarification, and Tyche mission plans.
- UI 👍/👎 → `POST /api/feedback` → configurable PostgreSQL feedback table.
- `scripts/enrich_layer_tags.py` — LLM-generated bilingual alias tags using catalog
  metadata plus MQS `property_list` field names/samples (dry-run by default;
  `--apply` writes; previous tags in `scripts/tags_backup.txt`).

---

## Providers

The catalog's `provider` column routes each layer to a registered adapter
([`registry.py`](app/dal/providers/registry.py), wired in `main.py`). **Production
registers `mqs`, `cubes`, and `tyche`** — `arcgis` is not a real provider anymore.
Layer selection and explicit-plan validation ignore catalog rows whose provider is not
registered, while the catalog UI still lists them for repair/editing. If no queryable
layers remain, selection returns a clarification instead of failing during planning.

Provider modules follow one-class-per-file composition. The public provider classes are
thin use-case coordinators; source parsing, request building, HTTP/pagination, response
mapping, schema inference, and dense-result splitting live in named collaborators such as
`MqsGateway`, `MqsEntityStream`, `CubesQueryBuilder`, `CubesSchemaMapper`,
`TycheGateway`, and `TycheFeatureMapper`. Provider files stay below 250 lines, and new
provider behavior belongs in the collaborator that owns that single responsibility.

- **`mqs`** — [`provider.py`](app/dal/providers/mqs/provider.py): the MQS (Moria Query Service)
  REST API. Catalog rows store `source_url = "mqs://layer/{layerId}"` (base-URL-
  independent; the live base URL is the `mqs_base_url` setting, read per call —
  unset means the provider errors with a clear message → HTTP 502). MQS layers are not
  mirrored into process memory. Query-time loading pushes the request boundary to
  `POST /MoriaProject/{id}/Entities`, follows only the bounded result pages,
  and follows `GET /MoriaProject/{id}/EntityInfo/{entity_id}` (a distinct route from
  `/Entities`, confirmed against a real MQS client — not a sub-path of it) to flatten
  each entity's `property_list` into normal feature columns. EntityInfo enrichment is
  best-effort: a failed detail call is logged and falls back to the `/Entities` row
  instead of failing the complete request with HTTP 502. Those columns drive schema
  discovery, value sampling, metadata/tag generation, attribute filters, displayed
  results, and every spatial operation. Property parsing accepts objects, name/value
  arrays, camel/Pascal-case names, nested wrappers, and JSON-encoded strings. Fixed
  transport fields (`triangle`, `clearence_level`, `source_id`, `date`, `area`,
  `perimeter`) remain queryable but have `metadata_relevant=false`; description/tag
  generation receives only business `property_list` fields and fails if none are found
  rather than producing polygon/clearance tags. Schema and planner logs expose
  discovered field names and bounded sample counts for diagnosis. Viewport/polygon
  filters are pushed down with POST for every query layer and are always rechecked
  locally before GeoDataFrame construction, even if MQS ignores the filter. A plan's
  `eq`-operator `attribute_filter` steps are pushed down the same way, as
  `simple_operators.match` in the same POST body (merged with any geometry filter);
  this is also always an optimization — `attribute_filter` still re-filters
  client-side, so an MQS instance that ignores the match body stays correct, just
  slower fetching more entities than necessary. Only `eq` maps to pushdown; `neq`,
  `gt`, `lt`, `contains`, and `fuzzy_contains` stay entirely client-side. A response
  whose `total_entities` exceeds one 10,000-row page is partitioned recursively into
  geographic quadrants, including when the original polygon is physically small but
  dense. Results are deduplicated by `entity_id`; partitioning stops if child regions
  do not reduce the reported load, recursion is bounded, a single layer load is capped
  at 10,000 distinct features, and one query may return at most 50,000 distinct
  features overall.
  `near`/`near_all` target loads use the request geometry expanded in a local metric CRS,
  avoiding a complete target-layer load without excluding any possible match. The
  `AILOCATOR_MQS_DETAIL_CONCURRENCY` setting bounds detail fan-out and is listed in
  `.env.example`.

- **`cubes`** — [`provider.py`](app/dal/providers/cubes/provider.py): time-varying entity
  locations such as buses. Rows use `source_url="cubes://db/<dbname>"`. The provider
  reads metadata with `GET /cube/v1/<dbname>` and falls back to
  `GET /cube/v1/<dbname>/parameters` when parameter definitions are not embedded.
  Name-only entries are hydrated through
  `GET /cube/v1/<dbname>/parameters/<parameterName>` so required flags, types,
  options, roles, and defaults are known before any row request.
  It posts metadata-driven temporal payloads to `/cube/v1/<dbname>`, sends the write-only
  Authorization token, and converts WKT POINT geometry to WGS84. Declared fields are
  merged with every non-geometry JSON key discovered dynamically; types, samples, and
  the temporal field are inferred and cached. Exact `<name>.match` and `<name>.not`
  names are preserved. `.match` receives the plan's ISO `From`/`To` range, `.not`
  receives the relative time-back shape, and an unsuffixed parameter keeps the legacy
  plain/`.not` pair. User geometry is sent through the available temporal parameter's
  `Location` and is rechecked locally before applying a result limit.
  A non-empty metadata `Value` is preserved and sent under the parameter's exact name
  on every request, satisfying required fixed parameters such as `environment=prod`.
  Configured values are excluded from model-facing schema serialization.
  Required selectors with options and dynamic selectors are resolved during the
  two-phase catalog flow, then stored in `source_url` as exact `param_<name>` values.
  New requests use `cubes_parameters`; `cubes_dynamic_parameters` is retained for
  compatibility. A declared `polygon` receives `{"value": [<boundary WKT>]}` and a
  plain `date` receives `{"TimeBackUnit":"no_time","TimeBackValue":1}`.
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
  Dynamic parameter names are arbitrary (for example `vehicleType` or `fl:dynamic`).
  Metadata can identify them with `Role=dynamic` or a `:dynamic` suffix; if metadata omits
  one, the catalog accepts its exact name manually and the provider injects the resolved
  value even without a parameter definition. A dynamic selector is backed by a child
  autocomplete cube — its declared `Options` are unusable placeholders
  (`LayerParameter.is_dynamic` marks it and drops those options). The exact name is
  preserved in the final request body. Valid values come only from
  `POST /cube/v1/<dbname>/autocomplete/<parameterName>`
  (`CubesProvider.fetch_autocomplete_options`, never cached — these cubes can change
  schema), exposed to the catalog UI via `POST /api/layers/autocomplete-parameter`.
  Metadata generation discovers unresolved dynamic parameters without fetching rows;
  after the UI resolves them, a second metadata request samples the normal cube route
  with those values in its request body.
  Resolution happens once at layer-add time, not per query: the user's chosen
  `{parameter_name: value}` map is folded into `source_url` as `param_<name>=<value>`
  query params (`cubes_resolved_parameters`), the same mechanism `query_mode` already
  uses. A required dynamic parameter with no resolved value fails loudly at fetch time.

- **`tyche`** — [`provider.py`](app/dal/providers/tyche/provider.py): the Our Forces API at
  `POST /coordinate/v1/ourforces`. Catalog rows use
  `source_url="tyche://ourforces"`; the live base URL, `username` header,
  write-only `Authorization` token, and TLS verification setting are read on
  every request. The adapter is request-scoped and stores no entity mirror.
  Every fetch sends Tyche's required `eventTime.match.gte/lte` values in
  `YYYY-MM-DD HH:mm:ss.SSS` format. An explicit plan `temporal_filter` is pushed
  into that request; otherwise the provider asks for the hour ending at the
  executor's current time. A WGS84 request boundary is sent as the documented
  `location` object with polygon WKT and is rechecked locally for correctness.
  The supplied ReDoc extract omitted the inner `location` schema, so its inferred
  `{ "match": "<WKT>" }` encoding is intentionally isolated in
  `TycheQueryBuilder` for a local adjustment against the full OpenAPI schema.
  Responses accept WKT, GeoJSON objects/strings, nested geometry values, and
  longitude/latitude objects, preserving the parsed value as the GeoDataFrame
  geometry. The provider follows `hasMoreResults`/`pageTracker`, requests only
  the remaining rows for bounded samples, deduplicates event IDs, rejects broken
  or repeated paging tokens, and stops at a 100,000-row safety ceiling.
  `POST /api/layers/activate-tyche` (the Layers UI's Tyche activation button)
  first probes one bounded entity and then idempotently upserts the canonical
  `כוחותינו` catalog row. Activation adds a detailed Hebrew capability description
  and bilingual selection tags; existing custom metadata is preserved and missing
  defaults are merged in. Failed configuration/API probes never modify the catalog.

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
UI values remain live overrides. MQS, Cubes, and Tyche verify TLS certificates by
default. Cubes and Tyche Authorization tokens have write-only API/UI semantics.

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
docker exec ailocator-backend python scripts/eval_build_plan.py
```

Requires: local Postgres `gis` DB with the `public.layers` catalog, and Ollama listening
on all interfaces (`OLLAMA_HOST=0.0.0.0:11434 ollama serve`) signed in for cloud models.
Inside the container the host is `pghost` (host-gateway) — `host.docker.internal` breaks on IPv6.

**Python 3.8 constraints:** no `match`, no `X | Y` unions, no builtin generics in
annotations that pydantic/FastAPI evaluate — use `typing.Optional/Union/List/Dict`.

## Tests

`tests/` runs without Postgres or an LLM: fakes implement the context-owned BL protocols
(this is DIP paying rent). Mock data lives in `data/*.geojson`; accident timestamps are
generated relative to `now`, which tests freeze (`frozen_now` fixture). Golden plans:
`tests/fixtures/plans/`.

The production image installs runtime dependencies only, copies only `app/`, and
runs as an unprivileged `app` user. Tests, scripts, and fixture data are excluded.

## Roadmap

1. Multi-turn clarify (conversation state), `client_now`/timezone in the request.
2. SSE status streaming; real ArcGIS provider; PostGIS.
3. End-to-end scored eval for plan building (selection already has one).
