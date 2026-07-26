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

Each GIS adapter intentionally has two production classes: a `*Mapper` for all
input/output shapes and a `*Provider` for communication and use-case orchestration.

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

There are exactly two production classes:

- `MqsMapper` (`mapper.py`) parses the layer ID, builds geography/attribute filters,
  splits geometry, normalizes every `property_list` variant, maps WKT, and infers schema.
- `MqsProvider` (`provider.py`) owns HTTP, paging, adaptive quadrant loading, dedup,
  concurrent best-effort EntityInfo enrichment, sampling, and safety caps.

The preserved limits are 10,000 rows per page/layer and 50,000 per bounded request.
Provider geometry is always rechecked locally. Dense regions split only while child
loads shrink; cross-tile rows deduplicate by `entity_id`. EntityInfo still uses its
distinct route and falls back to the list entity on failure.

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

There are exactly two production classes:

- `TycheMapper` (`mapper.py`) parses `source_url`, validates field mappings, builds
  time/geography request bodies, parses geometry, deduplicates rows, and builds schemas.
- `TycheProvider` (`provider.py`) owns HTTP, `pageTracker` pagination, settings, local
  boundary recheck, samples, and the 100,000-row safety cap.

`tyche://ourforces` remains canonical. Custom layers may configure split time fields and
typed `param_<name>` values; they cannot replace time, geography, or paging fields.

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
system prompt merged into the user turn via `merge_system_into_user` (for
servers/models that reject a system role). Each rung is tried in order; a
`BadRequestError` falls through to the next, anything else aborts as `AgentError`.

Supporting collaborators:
- `completion_retry.py` — `create_with_retry` — bounded retry (`_ATTEMPTS=2`,
  `_DELAY_SECONDS=0.3`) for transient rate-limit/connection/timeout errors.
- `json_response_parser.py` — `extract_json` — strips code fences, falls
  back to the substring between the first `{` and last `}`.
- `message_merger.py` — `merge_system_into_user` — for rung 3 above.
- `model_id_extractor.py` — `extract_model_ids` — normalizes OpenAI/gateway/bare
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

`connect(store)` (`database/postgres.py`) — `psycopg` connection with
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
- `mqs/provider.py` keeps `mqs_layer_id` as a compatibility alias; new code should call
  `MqsMapper.layer_id`.
- Keep new GIS behavior in the existing mapper/provider pair; do not reintroduce
  one-use gateway, source, builder, stream, schema, or client-factory classes.
