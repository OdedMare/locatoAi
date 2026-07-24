# `app/dal/` — Data Access Tier

Read this when you're touching a GIS provider (MQS/Cubes/Tyche), the LLM client, or
Postgres access. See [`../index.md`](../index.md) for how this tier fits with `bl/`,
`service/`, and `common/`.

## What this tier is

The DAL **implements** the interfaces (`Protocol`s) owned by their BL contexts:
`Provider`, `ProviderRegistry`, `LLMClient`, `LayersRepository`. It is the only tier
allowed to speak HTTP to external GIS/LLM systems or SQL to Postgres. `bl` never
imports `dal` directly — everything is wired together in `app/main.py` /
`app/application_state_wiring.py` (the composition root).

Per the code-size standard in the root `CLAUDE.md`, each subsystem is split into
one-class-per-file collaborators coordinated by a thin top-level `*Provider` class.

```
app/dal/
├── database/postgres.py        shared PostgreSQL connection factory
├── catalog/layers_repository.py implements LayersRepository (public.layers)
├── feedback/feedback_repository.py persists 👍/👎 feedback
├── providers/
│   ├── mqs/                    MQS (Moria Query Service) adapter
│   ├── cubes/                  Cubes (time-varying entity) adapter
│   ├── tyche/                  Tyche (Our Forces) adapter
│   └── registry.py              InMemoryProviderRegistry
└── llm/
    └── openai_client.py        OpenAI-compatible LLMClient + supporting collaborators
```

## BL interfaces implemented here

- `Provider` — `describe_schema(layer) -> LayerSchema`,
  `fetch_features(layer, now=None, geometry=None, limit=None, attribute_filters=None) -> gpd.GeoDataFrame`,
  `sample_field_values(layer, field, limit=20) -> List[str]`.
- `ProviderRegistry` — `get(provider_name) -> Provider`, `has(provider_name) -> bool`.
- `LLMClient` — `complete_json(system, user) -> dict`, `list_models() -> List[str]`.
- `LayersRepository` — `list_layers()`, `get_layer(id)`, `add_layer(layer)`,
  `update_layer_metadata(id, name, description, tags)`, `upsert_layer(layer) -> (layer, created)`.

**Every provider constructor takes a `RuntimeSettingsStore`** (plus an optional
`httpx.BaseTransport` test seam, never used in production wiring) and re-reads
`settings_store.get()` on **every call** — this is what makes the Settings UI a live
override with no restart required.

## MQS provider — `providers/mqs/`

Pipeline: `MqsSource` (parse `source_url`) → `MqsGateway` (HTTP/pagination) →
`MqsEntityStream` (adaptive quadtree splitting/dedup/enrichment) → `MqsEntityMapper`
(schema mapping) → `MqsSchemaBuilder` (dynamic field inference), coordinated by
`MqsProvider` (implements `Provider`).

| File | Class | Role |
|---|---|---|
| `provider.py` | `MqsProvider` | Orchestrator |
| `source.py` | `MqsSource` | Parses `mqs://layer/<id>`; resolves the temporal field tag |
| `filter_builder.py` | `MqsFilterBuilder` | Builds the POST filter body (`geo_polygon`/`geo_bounding_box`, `simple_operators.match`); quadrant-splits a geometry |
| `gateway.py` | `MqsGateway` | HTTP boundary: GET/POST, pagination, `/MoriaProject/{id}/EntityInfo/{entity_id}` detail fetch, layer listing |
| `entity_stream.py` | `MqsEntityStream` | Adaptive quadtree splitting, cross-tile dedup by `entity_id`, concurrent detail enrichment, per-layer cap |
| `entity_mapper.py` | `MqsEntityMapper` | Normalizes entity JSON variants (`property_list` schema-agnostic parsing, WKT geometry) into GeoDataFrame records |
| `schema_builder.py` | `MqsSchemaBuilder` | Infers `LayerSchema` from enriched sample entities |

**`MqsProvider`** public methods: `describe_schema`, `fetch_features`,
`sample_for_metadata(layer, limit=100)` (used by catalog metadata generation — samples
`_METADATA_SAMPLE_SIZE=10` entities, preferring ones with real business properties),
`sample_field_values`, `list_remote_layers()` (MQS inventory browsing for the catalog UI).

**Where the documented MQS business rules live** (see root `CLAUDE.md` "MQS bounded
loading" / "MQS business metadata" sections):
- Quadtree splitting: `MqsEntityStream._geometry_region` / `_should_split` /
  `_split_chunks`, using `MqsFilterBuilder.split`. Bounded by `_MAX_SPLIT_DEPTH = 4`;
  splits only when `total > PAGE_SIZE(10000)` and the region actually shrank.
- Dedup by `entity_id`: `MqsEntityStream._bounded_query` (`seen_ids` set).
- 10,000-row page / per-layer cap: `MqsGateway.PAGE_SIZE = 10000`;
  `MqsEntityStream.MAX_FEATURES_PER_LAYER = 10000` in `_validate_layer_cap`.
- 50,000-feature query-wide ceiling: `MqsGateway.MAX_FEATURES = 50000`.
- Local re-intersection regardless of remote filter honoring:
  `MqsEntityMapper.to_gdf(..., boundary=...)`.
- `eq`-only `attribute_filter` pushdown as `simple_operators.match`:
  `MqsFilterBuilder._attributes`, merged into the same POST body by `.build()`.
- EntityInfo enrichment is best-effort: `MqsGateway.entity_detail` → `_safe_detail`
  catches `ProviderError`, falls back to the `/Entities` row — never raises 502 for a
  detail-fetch failure.
- `property_list` variant parsing (object/name-value-array/camel-Pascal/nested/JSON
  string): `MqsEntityMapper.property_attributes` → `_decode_properties`.
- Fixed transport fields with `metadata_relevant=False`: `MqsEntityMapper.FIXED_FIELDS`
  (`triangle`, `clearence_level`, `source_id`, `date`, `area`, `perimeter`).
- `geo_bounding_box` vs `geo_polygon` choice: `MqsFilterBuilder._geometry`.

## Cubes provider — `providers/cubes/`

Pipeline: `CubesSource` (parse `cubes://db/<name>` + query params) →
`CubesClientFactory` (authenticated httpx client) → `CubesMetadataGateway` (+
`CubesParameterLoader`) for `/cube/v1/{cube}` and `/parameters` discovery →
`CubesQueryBuilder` (request body construction) → `CubesGateway` (POST +
capped-result recursive chunking) → `CubesSchemaMapper` (response/metadata → schema/
GDF), coordinated by `CubesProvider` (implements `Provider`).

| File | Class | Role |
|---|---|---|
| `provider.py` | `CubesProvider` | Orchestrator |
| `source.py` | `CubesSource` | Parses `cubes://db/<dbname>`, `query_mode`, `param_<name>=<value>` resolved-parameter map |
| `client_factory.py` | `CubesClientFactory` | Authenticated `httpx.Client` (Bearer token, TLS verify) |
| `metadata_gateway.py` | `CubesMetadataGateway` | `GET /cube/v1/{cube}` metadata (cached per db), `POST /cube/v1/{cube}/autocomplete/{param}` (never cached) |
| `parameter_loader.py` | `CubesParameterLoader` | Hydrates name-only parameter entries via `GET /cube/v1/{cube}/parameters/{name}` |
| `query_builder.py` | `CubesQueryBuilder` | Builds request bodies (`.match`/`.not`, polygon, `Location`), chunk splitting, required-parameter validation |
| `gateway.py` | `CubesGateway` | POSTs rows, recursive capped-result recovery (spatial then temporal chunking) |
| `schema_mapper.py` | `CubesSchemaMapper` | Maps metadata/params/response rows into `LayerSchema`/`LayerField`/`LayerParameter`/GeoDataFrame; dedup |

**`CubesProvider`** public methods: `describe_schema`,
`list_dynamic_parameters(layer)` (params with `is_dynamic=True`),
`list_configurable_parameters(layer, refresh=False)` (params the catalog UI must
resolve), `requires_geometry(layer)`, `fetch_features(layer, now=None, geometry=None,
limit=None, temporal_range=None)`, `sample_for_metadata(layer, limit=100,
geometry=None)`, `sample_field_values`, `fetch_autocomplete_options(layer,
parameter_name)` (live, never cached).

**Where the documented Cubes rules live** (see root `CLAUDE.md` "Cubes catalog
workflow" / "Cubes dynamic parameters" / "Cubes result cap" sections):
- Metadata discovery + `/parameters` fallback: `CubesMetadataGateway.metadata` merges
  `CubesParameterLoader.load`'s fallback fetch.
- Name-only parameter hydration: `CubesParameterLoader._is_complete` / `_definition`.
- `.match`/`.not` suffix + legacy payload: `CubesQueryBuilder.parts`, `_query_keys`,
  `_declared_keys`, `_DEFAULT_KEYS`; mode from `CubesSource.query_mode`
  (`auto`/`match_not`/`legacy`).
- Temporal range → `.match` From/To; geography via the temporal param's `Location`:
  `CubesQueryBuilder._absolute_window`, `_add_geometry`/`_location_key`.
- Dynamic parameters (`Role=dynamic` or `:dynamic` suffix, unusable declared options
  dropped): `CubesSchemaMapper._metadata_parameter`.
- `param_<name>=<value>` resolved-parameter encoding in `source_url`:
  `CubesSource.resolved_parameters` / `PARAMETER_PREFIX="param_"`, consumed by
  `CubesQueryBuilder.resolve_parameters`.
- `polygon` param → `{"value": [WKT]}`; plain `date` → `no_time` shape:
  `CubesQueryBuilder._add_geometry` / `_parameter_value`.
- Configured `Value` injected unchanged (e.g. `environment=prod`), excluded from
  model-facing serialization: `CubesQueryBuilder._apply_configured` +
  `LayerParameter.configured_value` (`Field(exclude=True)`).
- Required parameter with no value fails loudly: `CubesQueryBuilder._validate_required`
  raises `ProviderError`.
- `ResultsLimit` default 10,000: `CubesSchemaMapper.results_limit`.
- Result cap → adaptive quadtree of saturated tiles + dedup:
  `CubesGateway._fetch` → `_spatial_chunks` (bounded `_MAX_CHUNK_DEPTH=5`) or
  `_split_unbounded` → `_temporal_chunks`; dedup via `CubesSchemaMapper.deduplicate`.
- 100,000-row safety ceiling: `CubesGateway._MAX_ROWS = 100000`.

## FLAPI provider — `providers/flapi/`

`FlapiProvider` is the main provider facade for both Cube and Flow Package resources.
It dispatches `flapi://cube/<name>` to `CubesProvider` and
`flapi://package/<packageId>` to `FlowPackageProvider`; the registry keeps the legacy
`cubes` alias for existing catalog rows.

Flow Package pipeline: `FlapiSource` parses persisted typed inputs and selected queries
→ `FlowPackageGateway` fetches `/package/v1/quick/{id}` and executes
`/package/v3/{id}` → `FlowPackageMetadata` normalizes grouped definitions →
`FlowPackageSerializer` validates exact text/number/boolean/WKT/time shapes →
`FlowPackageProvider` maps each query result with `CubesSchemaMapper`. With no selected
query execution requests `lastQueries=true`. Each row carries `_package_query`;
partial-success trace IDs and query result-limit warnings are logged.

## Tyche provider — `providers/tyche/`

Simpler single-source provider (`tyche://ourforces` only).

| File | Class | Role |
|---|---|---|
| `provider.py` | `TycheProvider` | Orchestrator; validates `source_url == tyche://ourforces` |
| `gateway.py` | `TycheGateway` | `POST /coordinate/v1/ourforces`, `pageTracker` pagination, dedup, safety cap |
| `query_builder.py` | `TycheQueryBuilder` | Builds `eventTime.match` window, `location.match` WKT, `pageTracker` |
| `feature_mapper.py` | `TycheFeatureMapper` | Parses varied geometry encodings; row dedup by `id` |
| `schema_builder.py` | `TycheSchemaBuilder` | Fixed field list (`eventTime`, `callSign`, `forceType`, `unit`, `netId`, ...) + discovered extras |

`TycheProvider` caches the last 100 fetched rows per layer for schema description.
`TycheGateway._MAX_ROWS = 100000` safety cap; repeated `pageTracker` raises
`ProviderError`; page size 10,000 — same pagination/cap/dedup pattern as MQS/Cubes.

## Provider registry — `providers/registry.py`

`InMemoryProviderRegistry` (implements `ProviderRegistry`): plain `Dict[str, Provider]`.
`register(name, provider)` is called from `main.py`/`application_state_wiring.py`
(OCP: a new provider is one `register()` call). `get(name)` raises `ProviderError` if
unregistered. `has(name)` — used by `CatalogService.list_queryable_layers` to hide
layers whose provider isn't active in this process.

## LLM client — `llm/`

**`OpenAIJsonClient`** (`openai_client.py`, implements `LLMClient`) — targets OpenAI and
OpenAI-compatible servers (Ollama/vLLM/Groq); primary target is Gemma via Ollama.
- `complete_json(system, user) -> dict` — builds `[system, user]` messages, retries the
  JSON parse once (`_MAX_JSON_ATTEMPTS = 2`) with the parse error appended before
  raising `AgentError`; attaches `_usage` (token counts) when the provider reports them.
- `list_models(base_url_override=None, api_key_override=None) -> List[str]` — hits
  `GET {base}/models` directly via httpx (not the SDK) so Settings-panel values can be
  tested before saving.

**The degradation ladder** (`_attempts`, executed by `_complete`): 1) JSON mode
(`response_format: json_object`) → 2) plain (no response_format) → 3) plain with the
system prompt merged into the user turn via `MessageMerger.merge_system_into_user` (for
servers/models that reject a system role). Each rung is tried in order; a
`BadRequestError` falls through to the next, anything else aborts as `AgentError`.

Supporting collaborators:
- `completion_retry.py` — `CompletionRetry.create` — bounded retry (`_ATTEMPTS=2`,
  `_DELAY_SECONDS=0.3`) for transient rate-limit/connection/timeout errors.
- `json_response_parser.py` — `JsonResponseParser.parse` — strips code fences, falls
  back to the substring between the first `{` and last `}`.
- `message_merger.py` — `MessageMerger.merge_system_into_user` — for rung 3 above.
- `model_id_extractor.py` — `ModelIdExtractor.extract` — normalizes OpenAI/gateway/bare
  list/keyed-item model list shapes into a sorted, deduplicated set.

One `OpenAI` SDK client is cached per `(api_key, base_url)` to avoid a handshake per
round-trip in the multi-call agent pipeline — but `RuntimeSettingsStore.get()` is still
read fresh on every `complete_json` call. `llm_diet_mode` caps completion tokens at
`_DIET_MAX_COMPLETION_TOKENS = 1200`.

## Catalog repository & Postgres — `catalog/`, `database/`

**`PostgresLayersRepository`** (implements `LayersRepository`) — the only DAL module
that writes SQL. Owns table `public.layers` (name from runtime settings,
identifier-validated + quoted via `settings.quoted_layers_table()`), columns `id, name,
description, tags, provider, source_url`.
- `list_layers()`, `get_layer(layer_id)`.
- `add_layer(layer)` — INSERT; raises `ValueError` on `UniqueViolation`.
- `update_layer_metadata(layer_id, name, description, tags)` — UPDATE; raises
  `ValueError` if the row doesn't exist.
- `upsert_layer(layer) -> (layer, created)` — keyed on `(provider, source_url)`; on
  update **only `name`/`description` are touched — tags are preserved** because they
  may be LLM-enriched post-sync.

`PostgresConnection.connect(store)` (`database/postgres.py`) — `psycopg` connection with
`dict_row` factory. Host/port/database/user/password can be set individually in
runtime settings, overriding the equivalent parts embedded in `database_url`; blank
overrides fall back to the URL.

## Feedback repository — `feedback/feedback_repository.py`

**`PostgresFeedbackRepository`** — persists 👍/👎 from the UI. It is attached by the
composition root and consumed by `service/feedback/router.py`.
`add(query, verdict, selected_layers, reasoning, clarify, timestamp)` lazily
`CREATE TABLE IF NOT EXISTS` (name from `settings.quoted_feedback_table()`) then
INSERTs. Per root `CLAUDE.md`, downvotes here are meant to be mined as new cases for
`backend/scripts/eval_select_layers.py`.

## Notes for a new developer

- `app/dal/__init__.py`, `providers/__init__.py`, `llm/__init__.py` are empty — import
  concrete modules directly, no package-level re-exports.
- `mqs/provider.py` and `cubes/provider.py` keep a few module-level compatibility aliases at the bottom
  (e.g. `mqs_layer_id`, `cubes_database_name`, `DYNAMIC_PARAM_PREFIX`) for backward
  compatibility with older imports/tests — prefer the class methods
  (`MqsSource.layer_id`, `CubesSource.database_name`) in new code.
- Provider files stay below ~250 lines per the root `CLAUDE.md` code-size standard; new
  provider behavior belongs in the collaborator that owns that single responsibility,
  not bolted onto the orchestrator class.
