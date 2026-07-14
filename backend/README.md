# AiLocator Backend

FastAPI service that turns **natural-language geographic questions** (Hebrew/English) into
validated **Geo Query Plans** executed against GIS data with GeoPandas.

```
"תמצא את בית הקולנוע הכי צפוני"
        │
        ▼
POST /api/query {query, boundaries: MultiPolygon|null}
        │
        ▼
┌─ QueryOrchestrator ────────────────────────────────────────────┐
│  1. select layers   (LLM call 1 — LIVE)                        │
│  2. build plan      (LLM call 2 — NEXT STAGE)                  │
│  3. validate plan   (retry once with the error, then clarify)  │
│  4. execute plan    (GeoPandas ops, EPSG:2039 for meters)      │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
{status, features: GeoJSON, plan, selected_layers, reasoning, timing_ms}
```

The model never writes SQL and never invents data sources: it chooses from a
**Postgres layer catalog** and emits a **plan** — a small, validated JSON program
over six spatial operations.

---

## Architecture: N-tier + SOLID

Dependency direction: **service → bl ← dal**. The BL owns its interfaces
([`bl/ports.py`](app/bl/ports.py)); the DAL implements them; only
[`main.py`](app/main.py) (composition root) knows every tier.

```
app/
├── main.py                  # composition root: wiring + error mapping, nothing else
│
├── service/                 # ── HTTP tier: routers + DTOs, zero logic ──
│   ├── dto.py               # request/response models; QueryResponse.from_outcome()
│   ├── query_router.py      # POST /api/query           (NL entry point)
│   ├── plan_router.py       # POST /api/execute-plan    (debug: run a raw plan)
│   ├── agent_router.py      # POST /api/select-layers   (debug: LLM call 1 only)
│   ├── catalog_router.py    # GET/POST /api/layers + POST /api/layers/sync-mqs
│   ├── settings_router.py   # GET/PUT /api/settings     (backs the UI ⚙ panel)
│   ├── feedback_router.py   # POST /api/feedback        (👍/👎 → feedback.jsonl)
│   └── deps.py              # FastAPI dependency accessors (app.state)
│
├── bl/                      # ── Business logic tier ──
│   ├── ports.py             # Protocols the BL depends on (DIP):
│   │                        #   LayersRepository, Provider, ProviderRegistry, LLMClient
│   ├── query_orchestrator.py# the select → plan → validate → execute flow + retry policy
│   ├── agent/
│   │   ├── select_layers.py # call 1: catalog → prompt → layer ids (drops hallucinated ids)
│   │   ├── build_plan.py    # call 2: query+schemas → plan (+ sample_field tool rounds)
│   │   └── prompts/         # prompts are FILES; tuning ≠ code change
│   ├── plan/
│   │   ├── models.py        # GeoQueryPlan: discriminated union of 6 step types
│   │   └── validators.py    # semantic checks with agent-readable error messages
│   ├── executor/
│   │   ├── engine.py        # runs steps in order, dispatches via the op registry
│   │   └── ops/             # ONE module per op, self-registering (@register_op)
│   └── catalog/
│       ├── catalog_service.py # layer lookup + schema cache (TTL; stale beats failed)
│       └── mqs_sync.py      # MQS layer inventory → catalog upserts (tags preserved)
│
├── dal/                     # ── Data access tier (implements bl.ports) ──
│   ├── layers_repository.py # Postgres public.layers — the ONLY module with SQL
│   ├── providers/
│   │   ├── arcgis_mock.py   # TEST FIXTURE ONLY — used by tests/conftest.py, not production
│   │   ├── mqs.py           # MQS (Moria Query Service) REST adapter — the only prod provider
│   │   └── registry.py      # provider name → adapter instance
│   └── llm/
│       └── openai_client.py # OpenAI-compatible JSON-mode client (Ollama/Gemma today)
│
└── common/                  # ── Cross-cutting, no business rules ──
    ├── config.py            # env defaults (AILOCATOR_*, OPENAI_API_KEY)
    ├── runtime_settings.py  # UI-editable settings; JSON file overrides env
    ├── errors.py            # domain exceptions (mapped to HTTP in main.py)
    ├── geo.py               # CRS helpers — ALL meters math goes through here
    └── logging.py           # structlog → logs/requests.jsonl
```

**How SOLID maps onto it**

| Principle | Where it lives |
|---|---|
| SRP | routers translate HTTP only; each executor op is one module; the repository only speaks SQL |
| OCP | new op = new file in `executor/ops/` (engine untouched); new provider = one `register()` call |
| LSP/ISP | `Provider` is three methods (`describe_schema`, `fetch_features`, `sample_field_values`) — any adapter drops in |
| DIP | BL imports nothing from DAL; it depends on `bl/ports.py` Protocols, wired in `main.py` |

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
| `within_geometry` | keep features intersecting the request boundaries | rejected if request has no boundaries |
| `attribute_filter` | `eq/neq/gt/lt/contains` on a property | field must exist |
| `near` | keep features ≤ `distance_m` from any target-layer feature | reprojects to EPSG:2039 first |
| `directional` | N most northern/southern/eastern/western | projected centroids |
| `temporal_filter` | ISO `from`/`to` on the `timestamp` field | mock data is relative-to-now |

**Locked decisions** (don't relitigate): plans not SQL · meters math only after
reprojecting to EPSG:2039, never in WGS84 degrees · provider/catalog text is untrusted
prompt input (sanitized + truncated) · clarify is a first-class response, always Hebrew.

---

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
values of that field (JSON-protocol tool — the client is JSON-mode-only). Max 2 rounds
per query, separate from the validation retry; rounds are reported as `tool_calls` in
the response and listed in the UI agent panel. Backed by `Provider.sample_field_values`
(mock: distinct GeoJSON values; MQS: `ValueList`, falling back to an entities page).

**Model:** Gemma 4 31B via Ollama cloud (`gemma4:31b-cloud`), configured in the UI ⚙ panel.
The [LLM client](app/dal/llm/openai_client.py) is OpenAI-compatible and key-optional when a
`base_url` is set, with a degradation ladder: JSON mode → plain → system-merged-into-user.

**Quality loop:**
- `scripts/eval_select_layers.py` — SCORED eval (20 Hebrew/English cases with expected
  layer sets, incl. typos/slang/must-clarify; exit 1 on regression). Run after every
  prompt/model change. Add every real-world miss as a case.
- UI 👍/👎 → `POST /api/feedback` → `logs/feedback.jsonl` — mine downvotes for new cases.
- `scripts/enrich_layer_tags.py` — LLM-generated bilingual alias tags for the catalog
  (dry-run by default; `--apply` writes; previous tags in `scripts/tags_backup.txt`).

---

## Providers

The catalog's `provider` column routes each layer to a registered adapter
([`registry.py`](app/dal/providers/registry.py), wired in `main.py`). **Production
registers only `mqs`** — `arcgis` is not a real provider anymore.

- **`mqs`** — [`mqs.py`](app/dal/providers/mqs.py): the MQS (Moria Query Service)
  REST API. Catalog rows store `source_url = "mqs://layer/{layerId}"` (base-URL-
  independent; the live base URL is the `mqs_base_url` setting, read per call —
  unset means the provider errors with a clear message → HTTP 502). Fetching is
  fetch-all-filter-locally: `GET /MoriaProject/{id}/Entities` paginated
  (`geo_type=GeoJSON`, page 1000, hard cap 50k → error, never silent truncation);
  the executor does all spatial ops locally. Schemas come from
  `GET /MoriaProject/Layers/{id}` + best-effort `ValueList/{id}` samples. Response
  parsing is deliberately lenient (candidate-key lists) — no live MQS existed when
  written; adapting to a real instance stays inside `mqs.py`.

**Catalog sync:** `POST /api/layers/sync-mqs` (UI: button in the layers panel) pulls
`GET /MoriaProject/Layers` and upserts rows keyed on `(provider, source_url)` —
re-syncs update name/description in place and **preserve tags** (rerun
`scripts/enrich_layer_tags.py` after syncing new layers).

**`arcgis` / `MockArcgisProvider`** ([`arcgis_mock.py`](app/dal/providers/arcgis_mock.py))
is a **test fixture only** — it serves local `data/*.geojson` and backs
`tests/conftest.py`'s fixtures (so the suite runs without live MQS/Postgres) but
is never registered in production (`main.py`) or the eval script.

---

## Settings

Two layers, one store ([`runtime_settings.py`](app/common/runtime_settings.py)):

1. **Env defaults** — `AILOCATOR_*` vars / `OPENAI_API_KEY` ([`config.py`](app/common/config.py)).
2. **UI overrides** — whatever is saved in the ⚙ panel persists to `runtime-settings.json`
   (gitignored, mounted into the container) and **wins over env**.

Consumers read the store **per call** — settings changes need no restart.
The layers table name is identifier-validated and quoted before entering SQL.

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

`tests/` runs without Postgres or an LLM: fakes implement the `bl/ports.py` protocols
(this is DIP paying rent). Mock data lives in `data/*.geojson`; accident timestamps are
generated relative to `now`, which tests freeze (`frozen_now` fixture). Golden plans:
`tests/fixtures/plans/`.

## Roadmap

1. Multi-turn clarify (conversation state), `client_now`/timezone in the request.
2. SSE status streaming; real ArcGIS provider; PostGIS.
3. End-to-end scored eval for plan building (selection already has one).
