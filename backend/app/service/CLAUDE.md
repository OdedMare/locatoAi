# `app/service/` — HTTP Tier

Read this when you're adding/changing an API endpoint, a request/response DTO, or
touching the composition root. See [`../index.md`](../index.md) for how this tier fits
with `bl/`, `dal/`, and `common/`.

## What this tier is

Routers + DTOs. Routers should translate HTTP ↔ domain calls and contain no business
logic — real logic belongs in `bl/`. (Two routers currently deviate from this; see
"Zero-logic compliance" below — know about it, don't be surprised by it.)

## API endpoint table

| Method | Path | Request DTO | Response DTO | Purpose |
|---|---|---|---|---|
| GET | `/health` | — | `dict` | Liveness check (wired directly in `main.py`, not a router module) |
| POST | `/api/query` | `QueryRequest` | `QueryResponse` | Full NL pipeline: select layers → build plan → execute |
| POST | `/api/execute-plan` | `ExecutePlanRequest` | `QueryResponse` | Debug: validate + execute a hand-written plan, no LLM calls |
| POST | `/api/select-layers` | `SelectLayersRequest` | `SelectLayersResponse` | Debug: agent call 1 only |
| GET | `/api/layers` | — | `LayersResponse` | List catalog layers |
| POST | `/api/layers` | `CreateLayerRequest` | `CatalogLayer` (201) | Create a catalog layer; 409 on duplicate/invalid |
| PUT | `/api/layers/{layer_id}` | `UpdateLayerRequest` | `CatalogLayer` | Update name/description/tags |
| GET | `/api/layers/mqs` | — | `RemoteMqsLayersResponse` | Browse remote MQS inventory (not yet imported) |
| POST | `/api/layers/sync-mqs` | — | `MqsSyncResponse` | Upsert MQS inventory into the catalog |
| POST | `/api/layers/activate-tyche` | — | `CatalogLayer` | Probe + idempotently activate the Tyche "כוחותינו" layer |
| POST | `/api/layers/generate-metadata` | `GenerateLayerMetadataRequest` | `GeneratedLayerMetadataResponse` | LLM-suggest description/tags/parameters before creating a layer |
| POST | `/api/layers/autocomplete-parameter` | `CubesAutocompleteRequest` | `CubesAutocompleteResponse` | Live values for a Cubes dynamic parameter (never cached) |
| GET | `/api/settings` | — | `SettingsResponse` | Read runtime settings (secrets masked) |
| PUT | `/api/settings` | `SettingsUpdate` | `SettingsResponse` | Patch runtime settings (secrets write-only) |
| GET | `/api/models` | — | `ModelsResponse` | List models using saved settings |
| POST | `/api/models` | `ModelsProbeRequest` | `ModelsResponse` | List models using unsaved override URL/key |
| POST | `/api/feedback` | `FeedbackRequest` | `dict` | Persist a 👍/👎 verdict + selection context |

## Router-by-router

- **`query_router.py`** — `orchestrator.run_query(query, boundaries, event_sink=...)`.
  Validates/generates `X-Request-ID`, seeds `request.state.pipeline_trace`, wires a
  `QueryEventSink` so the orchestrator can stream trace events into it as it runs. On
  exception: logs then **re-raises** — HTTP mapping happens in the global
  `ErrorHandlerRegistry`, not here. Builds `QueryResponse.from_outcome(outcome)`.
- **`plan_router.py`** — `orchestrator.execute_plan(body.plan, boundaries)`. No LLM
  call; tests the executor in isolation.
- **`agent_router.py`** — `request.app.state.layer_selector.select(body.query)`
  (accessed directly off `app.state`, not through `deps.py`). Times the call locally
  purely for the response's `timing_ms`.
- **`catalog_router.py`** — the most logic-dense router; calls into `bl/catalog`,
  `bl/agent/generate_layer_metadata`, and `dal/providers/cubes`. See "Zero-logic
  compliance" below.
- **`settings_router.py`** — reads/writes `request.app.state.settings_store`. Owns all
  secret-masking logic (see "Settings secrets" below).
- **`feedback_router.py`** — `feedback_repository.add(**body.model_dump(),
  timestamp=utcnow())`. No `response_model` declared (returns a raw dict).
- **`models_router.py`** — `llm_client.list_models(...)`; POST passes
  `base_url_override`/`api_key_override` so the UI can test unsaved settings.

## `deps.py`

```python
class ServiceDependencies:
    @staticmethod
    def orchestrator(request: Request) -> QueryOrchestrator:
        return request.app.state.orchestrator

get_orchestrator = ServiceDependencies.orchestrator
```

Only **one** formal FastAPI dependency exists (`get_orchestrator`, used via
`Depends(...)` in `query_router.py`/`plan_router.py`). Every other router reads
`request.app.state.<thing>` directly as an ambient singleton — an intentional
inconsistency worth knowing about rather than "fixing" incidentally.

## Composition root: `app/main.py` + `app/application_state_wiring.py`

`ApplicationFactory.create()`:
1. `FastAPI(title="AiLocator", version="0.1.0")`.
2. `ApplicationStateWiring.wire(application, get_settings())` — builds the full
   dependency graph and attaches it to `app.state` (see below).
3. `ErrorHandlerRegistry.register(application)` — domain-error → HTTP-status handlers.
4. Includes all 7 routers + a direct `GET /health` (`HealthRouter.status`).

`ApplicationStateWiring.wire` in three phases:
1. **`_providers`** — `InMemoryProviderRegistry()`, registers `MqsProvider`,
   `CubesProvider`, `TycheProvider` (all take the shared `RuntimeSettingsStore`).
2. **`_services`** — `CatalogService`, `PlanExecutor`, `OpenAIJsonClient`,
   `RuntimeDietMode`, `LayerSelector`, `PlanBuilder`, `LayerMetadataGenerator`,
   `QueryOrchestrator`.
3. **`_assign`** — sets on `app.state`: `settings_store`, `repository`
   (`PostgresLayersRepository`), `feedback_repository`, `mqs_provider`,
   `cubes_provider`, `tyche_provider`, `catalog`, `layer_selector`, `llm_client`,
   `layer_metadata_generator`, `orchestrator`, `request_log`.

(`request.state.request_id` / `request.state.pipeline_trace` are separate, per-request,
set by `query_router.py` — not part of the composition root.)

### Error mapping — `error_handler_registry.py` + `error_handler.py`

| Exception (`app.common.errors.*`) | HTTP status |
|---|---|
| `LayerNotFoundError` | 404 |
| `PlanValidationError` | 422 |
| `ProviderError` | 502 |
| `ExecutionError` | 400 |
| `AgentError` | 503 |
| `Exception` (catch-all) | 500 |

Each `ErrorHandler(status_code)` logs `request_failed` via `app.state.request_log`,
returns `{"status": "error", "request_id", "detail", "error_type", "pipeline_trace"}`
(`detail` genericized only for the 500 catch-all), echoes `X-Request-ID` back. Routers
do **not** do their own try/except → HTTPException for these five types — the two
exceptions are `catalog_router.create_layer` (`ValueError`→409) and
`settings_router.update_settings` (`ValueError`→422), which are direct `HTTPException`
raises for validation failures, not domain errors.

## The `{query, boundaries}` contract

Confirmed exact shape — `dto/query_request.py`:
```python
class QueryRequest(BaseModel):
    query: str = Field(min_length=1)
    boundaries: GeoJSONMultiPolygon
```
`dto/geo_json_multi_polygon.py`:
```python
class GeoJSONMultiPolygon(BaseModel):
    type: Literal["MultiPolygon"]
    coordinates: List
    def to_shapely(self) -> BaseGeometry: ...
```
`type` is a `Literal["MultiPolygon"]` — a plain GeoJSON `Polygon` is rejected; callers
must wrap it. `coordinates` is untyped (`shapely.geometry.shape()` fails loudly at
`.to_shapely()` time if malformed). This DTO is reused by `ExecutePlanRequest` and
`GenerateLayerMetadataRequest.cubes_sample_boundary`.

## Settings secrets handling (`settings_router.py`)

**Read** (`GET /api/settings`): never returns plaintext secrets.
- `openai_api_key` → `openai_api_key_set: bool` + `openai_api_key_hint` (`mask_key()`:
  `None` if falsy, `"…{last 4 chars}"` if `len > 8`, else `"…"`).
- `cubes_token` / `tyche_token` → only `*_set: bool` booleans, no hint.
- `database_password` → only `database_password_set: bool`.
- `database_url` → `mask_db_password()` regex-masks the password segment
  (`(://[^:/@]+):[^@/]+@` → `\1:****@`), leaving user/host/db visible.
- `SettingsResponse` structurally cannot leak a secret — it has no raw secret fields at
  all, so masking is enforced by the DTO shape, not just by handler discipline.

**Write** (`PUT /api/settings`): secrets are write-only, blank means "keep current."
`_clean_patch()` strips `openai_api_key`/`database_password`/`cubes_token`/
`tyche_token` from the patch **only when submitted as `""`** (any non-empty string
overwrites). Same pattern for `llm_model`. The patch then goes through
`store.update(patch)`; a `ValueError` → `HTTPException(422)`.

## DTO modules

- **`dto/`** — core query/plan DTOs: `QueryRequest`, `GeoJSONMultiPolygon`,
  `QueryResponse` (built via `.from_outcome(QueryOutcome)`), `ExecutePlanRequest`,
  `FeatureCollectionMapper` (GeoDataFrame → GeoJSON, not a DTO), `SelectedLayerDto`.
- **`agent_dto/`** — `SelectLayersRequest`, `SelectLayersResponse`, `SelectedLayer`
  (agent call 1 in isolation).
- **`catalog_dto/`** — `CatalogLayer`, `CreateLayerRequest`, `UpdateLayerRequest`,
  `CubesParameterValues` (mixin: `cubes_parameters` / legacy `cubes_dynamic_parameters`,
  merge helper `.parameter_values()`), `CubesQueryMode` (`Literal["auto","match_not","legacy"]`),
  `CubesAutocompleteRequest`/`Response`/`OptionResponse`, `CubesParameterResponse`,
  `GenerateLayerMetadataRequest`, `GeneratedLayerMetadataResponse`, `LayersResponse`,
  `MqsSyncResponse`, `RemoteMqsLayerResponse`/`RemoteMqsLayersResponse`.
- **`models_dto/`** — `ModelsProbeRequest`, `ModelsResponse`.
- **`settings_dto/`** — `CatalogStatus`, `SettingsResponse` (no raw secrets — see
  above), `SettingsUpdate` (all-`Optional` patch payload, raw secrets accepted but
  never echoed back).
- **Top-level `service/`** — `feedback_request.py::FeedbackRequest`,
  `query_event_sink.py::QueryEventSink` (callable, appends to
  `request.state.pipeline_trace` and logs `query_pipeline`, passed as
  `orchestrator.run_query(event_sink=...)`).

## Zero-logic compliance — know these two exceptions

Most routers are clean delegates. Two carry real domain logic that a new developer
should expect to find, even though the project convention is "routers translate HTTP
only":

1. **`catalog_router.py`** — `normalized_source`, `with_cubes_mode`,
   `with_parameters`, `clean_tags`: URL-scheme construction/normalization for
   `cubes://`/`tyche://` source URLs and tag dedup/truncation. This is domain-specific
   transformation, not pure delegation — flagged here so it isn't mistaken for an
   accident when you go looking for where a `cubes://` URL gets built.
2. **`settings_router.py`** — `mask_key`, `mask_db_password`, `_clean_patch`: real
   regex/conditional logic for secret masking, isolated into static/classmethods.

If you're adding new logic to either router, prefer extending the existing isolated
helper over spreading more logic across the handler function.
