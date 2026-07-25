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

`FlapiProvider` wraps `FlowPackageProvider` directly — FLAPI serves Flow Package
resources only. The legacy `provider=cubes` catalog alias, cube-resource dispatch, and
`FlapiSource.resource_type()` have been removed; every `flapi://` source is a package.

Flow Package pipeline: the catalog UI persists three free-text cube names plus an input
kind in `source_url` — `input_cube_name`, `input_cube_parameter`, `input_cube_kind`
(`time` | `geo`, default `time`), and `output_cube_name`. `FlapiSource` reads them via
`package_input_cube_name` / `package_input_cube_parameter` / `package_input_cube_kind` /
`package_output_cube_name`. Only the input cube's `cube_parameter` varies per query;
every other package parameter is fixed inside the package itself, so nothing else is
serialized. **There is no raw-HTTP path left in this provider and no FLAPI route or API
version appears in the code** — flunks owns the whole conversation. Parameter discovery
(`GET /package/v1/quick/{id}`), `FlowPackageMetadata`, `FlapiSource.execution_params` /
`package_queries` / `package_inputs`, `list_configurable_parameters`,
`requires_geometry`, and the `httpx` transport seam are all gone; `FlapiClientFactory`
now only validates settings for `FlapiConfig`, and `FlapiProvider(settings_store)` takes
no transport. Because BL looks those up with `getattr`, the catalog UI's parameter form
is simply empty and `requires_sample_polygon` is always false. →
`FlowPackageSerializer.build_input_cube(name, parameter, kind, temporal_range, geometry,
now)` assembles one `flunks.PackageInputCube`: for `kind="time"` it sets
`start_time`/`end_time` from the query `temporal_range` (falling back to a 1-hour window
ending at `now` on the schema/sample path where no range exists); for `kind="geo"` it
passes the whole query boundary via `values` as a single-element list holding one WKT
`MULTIPOLYGON` containing every boundary polygon — one geographic layer is one flunks
identifier, so a multi-polygon boundary is one chunk, not one chunk per polygon. **There
is no empty-`values` fallback:** FLAPI rejects an empty main cube input ("Please enter
values for the main cube input"), so a missing boundary raises `ProviderError` naming the
fix. Because a package has no discovery call, `describe_schema` must *run* the package,
which is why `Provider.describe_schema(layer, geometry=None)` and
`CatalogService.get_schema(layer_id, geometry=None)` now forward the request boundary
(the schema cache keys on it, and `CatalogService._describe` inspects the provider
signature so implementations that ignore geometry keep their single-argument form). →
`FlowPackageGateway.execute(layer, input_cube, output_cube_name)` builds a
`flunks.config.FlapiConfig` from `RuntimeSettingsStore`
(`cubes_base_url`/`cubes_token`/`flapi_username`) and a
`flunks.config.FlunksPackageConfig(package_id, main_input_cube, output_cube)` with
`PackageOutputCube(cube_name=output_cube_name)` (no `cube_fields`, no
`static_parameters`), runs it through `flunks.FlunksRunner.run()` and reads
`runner.success_chunks`/`failed_chunks` for diagnostics. Each record is tagged with
`_package_query=<output_cube_name>`. `FlunksRunner.run()` returns a pandas/geopandas
DataFrame; any other type raises `ProviderError`. **Package results are never
row-capped**, so the `rows=` log is the only advance warning before a large frame is
materialized.

**`package_records.py`.** `FlowPackageRecords` converts three things that
`DataFrame.to_dict("records")` alone leaves unusable downstream:
- **shapely geometry → WKT.** `FlapiSchemaMapper._point` only parses a `str`, so an
  unconverted geometry object makes the layer return **zero features with no error** —
  the one failure here that is silent rather than loud.
- **`NaN` → `None`.** `NaN` passes every `value is not None` guard in schema inference,
  typing a gapped numeric column as `"string"` and leaking `"nan"` into agent prompts.
- **numpy scalars → Python natives.** `numpy.int64` fails `isinstance(value, int)` in
  `_field_type` and is not JSON-serializable.

Note that pandas widens an int column containing `NaN` to `float64` at construction, so
such a column arrives as floats regardless of this conversion.

**Debug logging (`package_debug.py`).** `FlowPackageDebug` renders bounded, log-safe
descriptions so a failed package run is diagnosable from the console alone. Grep these
prefixes, in pipeline order: `Schema describe` (BL, includes `has_geometry`) →
`FLAPI describe_schema` → `FLAPI fetch_features` → `FLAPI source` (parsed cube names +
`source_url`) → `FLAPI input cube BUILD`/`READY` → `FLAPI package CONFIG` (base URL and
`token_set`, never the token) → `FLAPI package RUN` → `CHUNKS`/`OK`/`FAILED`.
`fetch_features` logs `rows`/`mapped`/`after_intersect`/`returned` so rows lost to
geometry parsing are distinguishable from rows lost to the boundary intersect. An empty
input cube logs `values=EMPTY (FLAPI will reject this)`; WKT is truncated to 120 chars
with the total length, keeping geometry type and leading coordinates visible. Validation
errors include only their field paths/types and bounded input previews at normal log
levels; the full traceback is emitted only at `DEBUG`.

**`flunks_metadata_patch.py` — temporary upstream workaround.** flunks types
`FlowResults.metadata.isPartialSuccess` as `str`, but FLAPI sends a JSON boolean, and
pydantic v2 does not coerce `bool` -> `str`. Every successful package run therefore died
in flunks' *own* response parsing with `Input should be a valid string
[input_value=False]` at `flow_ops.run_package`, with `success=0 failed=0` because
`FlunksRunner._run_chunk` raises before either counter moves. `FlunksMetadataPatch.apply()`
widens that annotation to `Union[bool, str]` at `package_gateway` import time — there is
no seam inside `FlunksRunner` to intercept.

Two details are essential: Pydantic embeds child schemas, so `MetaData` must be rebuilt
*before* `FlowResults`; and the widened annotation must preserve `Optional[str]` rather
than replacing it. Reversing that rebuild order reproduces the original string error.
Field lookup accepts both `isPartialSuccess` and the snake-case model field
`is_partial_success`/camel-case alias used by some flunks builds.

The patch is idempotent, still accepts a string, and self-disables once `str` is no
longer among the field's admitted types. `package_gateway` **logs whether it applied**
(`FLAPI flunks metadata patch applied=`) — a no-op is otherwise indistinguishable from
success and resurfaces much later as a `FlowResults` `ValidationError`. Check that line
first when `isPartialSuccess` errors return.
**Delete the module and its import when flunks fixes the type upstream.**

Endpoint routing, chunking, retries, and exception mapping for the execution call are
owned by flunks. The gateway does not construct or inject `FlunksConfig` or
`FlunksExceptionsConfig`; passing an empty config from an incompatible build caused
`max_threads` attribute errors, while omitting both lets `FlunksRunner` own its matching
defaults. `flunks` is an internal library not resolvable from the public index — see
`pyproject.toml`; the amd64 Docker image builds against a private index, so the FLAPI
package tests cannot run in an environment without it.

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
