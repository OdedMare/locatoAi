# `app/dal/` — Data Access Tier

Read this when you're touching a GIS provider (MQS/FLAPI/Tyche), the LLM client, or
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
│   ├── flapi/                  Flow Package (FLAPI/flunks) adapter
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
  `update_layer_metadata(layer)`, `delete_layer(id)`,
  `upsert_layer(layer) -> (layer, created)`.

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

## FLAPI provider — `providers/flapi/`

There are exactly two production classes:

- `FlunksMapper` (`mapper.py`) parses `source_url`, builds the SDK's
  `FlunksPackageConfig` and input cube, normalizes the returned DataFrame, maps WKT
  points, and infers the layer schema.
- `FlapiProvider` (`provider.py`) reads username/token, builds `FlApiConfig` plus the
  required `FlunksConfig()`, runs `FlunksRunner`, logs safe identifiers, tracks chunks,
  filters the GeoDataFrame, and caches its schema.

The source URL stores `input_cube_name`, `input_cube_parameter`, `input_cube_kind`
(`time` or `geo`), and `output_cube_name`. Geographic input is one WKT
`MULTIPOLYGON`; time input uses the requested range or the previous hour. Required
values fail before the network call. The runner result must be a DataFrame; `NaN`,
numpy scalars, and shapely geometry cells are normalized before schema/GDF mapping.

`FLAPI flunks INPUT` logs package/cube/parameter/output identifiers and a bounded WKT
preview, but never the token. The small import-time `isPartialSuccess` compatibility
patch remains in `provider.py`; remove it when flunks accepts booleans upstream.
FLUNKS owns endpoint routing, chunking, and retries.

## Tyche provider — `providers/tyche/`

Tyche coordinate-layer provider. `tyche://ourforces` remains the canonical layer;
additional catalog rows carry their route and field mapping in `source_url`.

| File | Class | Role |
|---|---|---|
| `provider.py` | `TycheProvider` | Orchestrates configured Tyche catalog layers |
| `source.py` | `TycheSource` | Parses route, geometry/geography/time field overrides, split time fields, and typed fixed request parameters |
| `gateway.py` | `TycheGateway` | Posts to the configured route; `pageTracker` pagination, dedup, safety cap |
| `query_builder.py` | `TycheQueryBuilder` | Builds nested or split time fields, fixed parameters, geography, and `pageTracker` |
| `feature_mapper.py` | `TycheFeatureMapper` | Parses the configured geometry field; row dedup by `id` |
| `schema_builder.py` | `TycheSchemaBuilder` | Fixed Our Forces fields or sampled custom-layer fields |

`TycheProvider` caches the last 100 fetched rows per layer for schema description.
`TycheGateway._MAX_ROWS = 100000` safety cap; repeated `pageTracker` raises
`ProviderError`; page size 10,000 — same pagination/cap/dedup pattern as MQS.
Custom layers store split request-time names as `time_from_field`/`time_to_field` and
fixed body values as `param_<name>` in `source_url`. Both time names must be configured
together; fixed parameters cannot replace time, geography, or paging fields.

## Provider registry — `providers/registry.py`

`InMemoryProviderRegistry` (implements `ProviderRegistry`): plain `Dict[str, Provider]`.
`register(name, provider)` is called from `main.py`/`application_state_wiring.py`
(OCP: a new provider is one `register()` call). `get(name)` raises `ProviderError` if
unregistered. `has(name)` — used by `CatalogService.list_queryable_layers` to hide
layers whose provider isn't active in this process.

## LLM client — `llm/`

**`OpenAIJsonClient`** (`openai_client.py`, implements `LLMClient`) — targets OpenAI and
OpenAI-compatible servers (Ollama/vLLM/Groq); primary target is Gemma via Ollama.
- `complete_json(system, user, schema=None) -> dict` — builds `[system, user]` messages, retries the
  JSON parse once (`_MAX_JSON_ATTEMPTS = 2`) with the parse error appended before
  raising `AgentError`; attaches `_usage` (token counts) when the provider reports them.
- `list_models(base_url_override=None, api_key_override=None) -> List[str]` — hits
  `GET {base}/models` directly via httpx (not the SDK) so Settings-panel values can be
  tested before saving.

**The degradation ladder** (`_attempts`, executed by `_complete`): when supplied,
1) JSON Schema → 2) JSON mode (`response_format: json_object`) → 3) plain → 4) plain with the
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
- `update_layer_metadata(layer)` — UPDATE; raises
  `ValueError` if the row doesn't exist.
- `delete_layer(layer_id)` — DELETE returning the removed layer, or `None`.
- `upsert_layer(layer) -> (layer, created)` — keyed on `(provider, source_url)`; on
  update **only `name`/`description` are touched — tags are preserved** because they
  may be LLM-enriched post-sync.

`LayerMeta` exposes typed `entity_field`, `display_field`, and `profiles`. The repository
alone encodes/decodes those values as legacy semantic tags so existing six-column
catalog tables require no migration; business tags remain clean everywhere above DAL.

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
- `mqs/provider.py` keeps a few module-level compatibility aliases at the bottom (e.g.
  `mqs_layer_id`) for backward compatibility with older imports/tests — prefer the class
  methods (`MqsSource.layer_id`) in new code.
- Provider files stay below ~250 lines per the root `CLAUDE.md` code-size standard; new
  provider behavior belongs in the collaborator that owns that single responsibility,
  not bolted onto the orchestrator class.
