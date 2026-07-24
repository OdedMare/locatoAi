# `app/bl/` — Business Logic Tier

Read this when you're touching the plan contract, an executor op, the agent (LLM call)
pipeline, or the orchestrator. This is the largest and most important tier — the pure
business core. See [`../index.md`](../index.md) for how it fits with `dal/`,
`service/`, and `common/`.

## What this tier is

Pure business logic. No HTTP, no DB, no HTTP-client code of its own — `bl` owns the
abstract `Protocol` interfaces beside the context that uses them; `dal/` supplies the
concrete implementations, wired together in `app/main.py`. `bl` never imports `dal`
directly.

```
app/bl/
├── plan/
│   ├── models/                one Pydantic model per plan step + discriminated union
│   └── validators.py          semantic checks
├── executor/
│   ├── engine/                 dispatches steps via the op registry
│   └── ops/                    ONE module per op, self-registering (@register_op)
├── agent/
│   ├── llm_client.py           agent-owned LLM Protocol
│   ├── select_layers/          call 1: catalog → prompt → layer ids
│   ├── build_plan/             call 2: schemas → plan, tools, constraint preservation
│   ├── generate_layer_metadata/  provider sample → editable catalog metadata
│   └── prompts/                prompts are FILES; tuning ≠ code change
├── query_orchestrator/        select → plan → validate → execute → diagnose flow
├── providers/                 provider + registry Protocols used by the BL
└── catalog/
    ├── models/                 layer metadata/schema/parameter models
    ├── layers_repository.py    catalog-owned repository Protocol
    └── ...                     layer lookup, schema cache, MQS sync, Tyche activation
```

Dependency order within the tier: `plan` has no dependency on `executor`/`agent`;
`executor` depends on `plan.models` + `catalog` + `providers`; `agent` depends on
`plan`, `catalog`, and its `LLMClient` Protocol; `query_orchestrator` composes
`agent` + `catalog` + `executor`; `catalog` depends only on its repository Protocol
and the provider registry Protocol.

## 1. Context-owned models and Protocols — the DIP seam

Pure-data Pydantic models plus `typing.Protocol` interfaces. No implementation lives
here — `dal/` supplies it structurally (duck-typed, no explicit inheritance needed).

| File | Type | Abstract methods | Implemented by |
|---|---|---|---|
| `catalog/layers_repository.py` | `LayersRepository(Protocol)` | `list_layers()`, `get_layer(id)`, `add_layer(layer)`, `update_layer_metadata(id, name, description, tags)`, `upsert_layer(layer) -> (layer, created)` | `dal/catalog/layers_repository.py::PostgresLayersRepository` |
| `agent/llm_client.py` | `LLMClient(Protocol)` | `complete_json(system, user) -> dict`, `list_models() -> List[str]` | `dal/llm/openai_client.py::OpenAIJsonClient` |
| `providers/provider.py` | `Provider(Protocol)` — intentionally the whole surface (ISP) | declares pushdown `capabilities`; `describe_schema(layer) -> LayerSchema`; `fetch_features(..., attribute_filters=None, temporal_range=None)` (all are hints — correctness never depends on them); `sample_field_values(...)` | `FlapiProvider`, `MqsProvider`, `TycheProvider` |
| `providers/registry.py` | `ProviderRegistry(Protocol)` | `get(provider_name) -> Provider`, `has(provider_name) -> bool` | `InMemoryProviderRegistry` |
| `catalog/models/layer_meta.py` | `LayerMeta(BaseModel)` | data only — one catalog row: `id, name, description="", tags=[], provider, source_url` | n/a |
| `catalog/models/layer_schema.py` | `LayerSchema(BaseModel)` | data only: `layer_id, geometry_type, fields: List[LayerField], parameters: List[LayerParameter]=[], source_name="", source_description="", entity_field: Optional[str], temporal_field: Optional[str]` | n/a |
| `catalog/models/layer_field.py` | `LayerField(BaseModel)` | data only: `name, type, description="", samples: List[str]=[], metadata_relevant=True` | n/a |
| `catalog/models/layer_parameter.py` | `LayerParameter(BaseModel)` | data only: `name, type, display_name="", description="", required=False, single_value=True, options=[], is_dynamic=False, resolved_value=None, configured_value: Any` (excluded from serialization — may hold secrets) | n/a |
| `catalog/models/layer_parameter_option.py` | `LayerParameterOption(BaseModel)` | data only: `value, name=""` | n/a |

When you need to call a provider or the LLM or the catalog repository from `bl` code,
import the Protocol from its BL context, never the concrete `dal` class.

## 2. `bl/plan/` — the GeoQueryPlan contract

### `models/geo_query_plan.py`
```python
class GeoQueryPlan(BaseModel):
    explanation: str
    steps: List[Step]
    output: str            # step id that produces the plan's result
    context_layers: List[str] = []
```
`Step` (`models/step.py`) is `Annotated[Union[18 step classes], Field(discriminator="op")]`
— the discriminator field is **`op`**, a `Literal[...]` on every concrete step model.
This is the single place to touch when adding another step type.

### The 18 step types (`models/*_step.py`)

| Step model | `op` literal | Purpose |
|---|---|---|
| `LoadStep` | `load` | Fetch a layer's features from its provider — the only step with no `input`; starts a pipeline |
| `WithinGeometryStep` | `within_geometry` | Keep features intersecting the user-drawn polygon |
| `AttributeFilterStep` | `attribute_filter` | Filter rows by one field: `eq/neq/gt/lt/contains/fuzzy_contains` |
| `NearStep` | `near` | Keep features within `distance_m` of ANY feature in a target layer |
| `NearestNStep` | `nearest_n` | Keep the `count` globally-closest features to a target layer |
| `NearAllStep` | `near_all` | Require proximity to ALL of 2–5 named targets, rank/limit by mean distance |
| `BetweenStep` | `between` | Keep features inside a corridor of `corridor_width_m` between two reference layers |
| `CrossesStep` | `crosses` | Topological "crosses" against a target layer |
| `TouchesStep` | `touches` | Topological "touches" (boundary contact, no interior overlap) |
| `ContainsStep` | `contains` | Topological "contains" |
| `DirectionalStep` | `directional` | The `count` most N/S/E/W features by bounding-box center |
| `TemporalFilterStep` | `temporal_filter` | ISO `from`/`to` on the provider-declared time field |
| `ClusterStep` | `cluster` | Connected group of ≥ `min_group_size` mutually within `max_distance_m` |
| `LatestPerEntityStep` | `latest_per_entity` | Most-recent row per `entity_field` (by `time_field`) |
| `MovementDirectionStep` | `movement_direction` | Entities whose first→last position moved `min_distance_m`+ in a direction |
| `TrajectoryRelationStep` | `trajectory_relation` | Compare different entities' tracks in space/time using configurable buffers |
| `OriginMovementStep` | `origin_movement` | Detect departure from or return to an inferred starting point |
| `CountStep` | `count` | Terminal aggregation: row count as a plain `int`; must be the plan's final step |

`reference_entity_filter`, `union_find`, `proximity_result_builder` (in
`executor/ops/`) are **internal helpers**, not plan step types — no `Step` model.

Common pattern: every step has `id: str` and (except `LoadStep`) `input: str`
referencing an earlier step's `id`. Optional target-filter triples
(`field`/`operator`/`value`) always travel together — repeats across `NearStep`,
`NearestNStep`, `BetweenStep`, `NearAllStep`'s `ProximityTarget`, and
`SpatialRelationStep`.

Representative examples: `NearStep` — `distance_m: float = Field(default=300, gt=0, le=5000)`;
`MovementDirectionStep` — `direction: Literal["any","north","south","east","west"],
entity_field: str, time_field: str, min_distance_m: float =
Field(default=50, ge=0, le=50000)`; `LatestPerEntityStep` requires explicit
`entity_field` and `time_field` values from the selected layer schema.

### `validators.py` — `PlanValidator` / `validate_plan = PlanValidator().validate`

`validate(plan, known_layer_ids, has_user_geometry) -> None` (raises
`PlanValidationError`):

| Rule | Enforced by |
|---|---|
| Earlier references (`input`/`id` reference a prior step) | `_validate_identity` |
| Catalog IDs exist | `_known_layer`, called from `_validate_step`, `_validate_target_step`, `_validate_between`, `_validate_near_all` |
| Complete target filters (field/operator/value together) | `_complete_filter` |
| `within_geometry` present iff request has boundaries | `_validate_step` + `_validate_shape` |
| Final output ordering (`plan.output` is the last step) | `_validate_shape` |
| Terminal count (`count` step is sole output, never another step's `input`) | `_validate_count_steps` |

## 3. `bl/executor/` — the plan runner

### `engine/plan_executor.py` — `PlanExecutor`
```python
def __init__(self, catalog: CatalogService, providers: ProviderRegistry): ...
def execute(self, plan, user_geometry=None, now=None) -> Union[gpd.GeoDataFrame, int]
def execute_detailed(self, plan, user_geometry=None, now=None,
                      trace_sink: Optional[Callable[[dict], None]] = None) -> ExecutionOutput
```
Runs `plan.steps` in **list order** (validators guarantee this is already
topological). Dispatches via `get_op_handler(step.op).run(step, ctx)` — the engine has
zero per-op knowledge. Precomputes `load_temporal_ranges`/`load_attribute_filters` by
walking the plan backward from each `TemporalFilterStep`/`AttributeFilterStep`
(`eq` only) to its source `LoadStep`, as provider pushdown hints. Short-circuits on
`CountStep` — returns immediately, never writes into `ctx.results` (a count step can't
be another step's input, per `validators.py`). Emits per-step started/completed/failed
trace dicts to `trace_sink` when provided.

`engine/execution_output.py` — `ExecutionOutput` (`@dataclass`): `features`,
`scalar_result: Optional[int] = None`, `step_traces: List[Dict] = []`.

### `ops/base/` — the OCP self-registration mechanism

- **`op_handler.py`** — `OpHandler(ABC)`: one abstract method
  `run(self, step, ctx) -> Union[gpd.GeoDataFrame, int]`.
- **`op_registry.py`** — module-level `_REGISTRY: Dict[str, OpHandler]`;
  `register_op = OpRegistry.register`, `get_op_handler = OpRegistry.get` (raises
  `KeyError` if unregistered).
- **`op_registration.py`** — `OpRegistration`, the `@register_op("name")` decorator:
  instantiates the handler once and stores that single instance in the registry.

**How to add a new op** (the engine never changes): create a module under `ops/`,
subclass `OpHandler`, decorate with `@register_op("my_new_op")`, implement `run()`,
then add one import line to `ops/__init__.py` — `plan_executor.py` does
`import app.bl.executor.ops  # noqa: F401` specifically to run every `@register_op`
decorator at import time. You'll also need: the Pydantic step model, `step.py`'s Union,
`validators.py` if it needs semantic checks, `preserves_constraints.py`'s
`_CONSTRAINT_FIELDS` if it's constraint-bearing, a `plan-geo-queries` operation skill,
and prompt/trace/tests/docs updates. Both build prompt profiles consume the shared skill.

- **`execution_context.py`** — `ExecutionContext` (`@dataclass`), the state flowing
  between ops: `catalog`, `providers`, `user_geometry`, `now`, `results: Dict[str,
  gpd.GeoDataFrame]` (every completed step's output, keyed by step id — this resolves
  `input` references), `feature_cache` (memoizes `load_layer_features` by
  `(layer_id, geometry_wkb, temporal_range, attribute_filters)`),
  `load_temporal_ranges`/`load_attribute_filters` (precomputed pushdown hints). Key
  method `load_layer_features(...)` resolves the layer, reads the adapter's semantic
  capabilities (not its registered name), forwards supported temporal/attribute
  pushdowns, calls `provider.fetch_features`, tags `gdf.attrs["temporal_field"]`,
  caches. `proximity_geometry(distance_m)` buffers `user_geometry` (WGS84-safe, via
  `common/geo.py`) for proximity ops' target-layer pushdown hints.

### Every op

| File | Class | Handles | Purpose |
|---|---|---|---|
| `load.py` | `LoadOp` | `LoadStep` | Fetches via `ctx.load_layer_features` with precomputed pushdowns |
| `within_geometry.py` | `WithinGeometryOp` | `WithinGeometryStep` | `intersects()` the user polygon (reprojects to WGS84 defensively) |
| `attribute_filter.py` | `AttributeFilterOp` | `AttributeFilterStep` | `eq/neq/gt/lt/contains/fuzzy_contains` (fuzzy: `rapidfuzz.partial_ratio` ≥ 80 on normalized text) |
| `near.py` | `NearOp` | `NearStep` | Within `distance_m` of any target feature; reprojects to ITM (EPSG:2039) first |
| `near_all.py` | `NearAllOp` | `NearAllStep` | Proximity to ALL 2–5 targets, ranks by mean distance |
| `nearest_n.py` | `NearestNOp` | `NearestNStep` | Top-N via `sjoin_nearest` + `nsmallest` |
| `directional.py` | `DirectionalOp` | `DirectionalStep` | Ranks by WGS84 bbox center on N/S/E/W axis |
| `movement_direction.py` | `MovementDirectionOp` | `MovementDirectionStep` | Groups by entity, compares first vs last position; emits `movement_distance_m`, `movement_direction`, `movement_path` |
| `trajectory_relation.py` | `TrajectoryRelationOp` | `TrajectoryRelationStep` | Pairwise track comparison for together/destination/time/shared-place patterns; emits related ids and paths |
| `origin_movement.py` | `OriginMovementOp` | `OriginMovementStep` | Detects departures and round trips inside an explicit window; labels the origin as inferred |
| `latest_per_entity.py` | `LatestPerEntityOp` | `LatestPerEntityStep` | Sorts by time, drops duplicate entity keys keeping the latest |
| `cluster.py` | `ClusterOp` | `ClusterStep` | Buffer + `sjoin` self-join graph + `UnionFind`; tags `cluster_id` |
| `count.py` | `CountOp` | `CountStep` | `len(ctx.results[step.input])` as a plain `int` |
| `between.py` | `BetweenOp` | `BetweenStep` | Buffered line-corridors between target pairs; caps pair count at 2500 |
| `temporal_filter.py` | `TemporalFilterOp` | `TemporalFilterStep` | Filters by `gdf.attrs["temporal_field"]` within `[from_, to]` |
| `spatial_relation/spatial_relation_op.py` | `SpatialRelationOp` (base) | shared | `gpd.sjoin(gdf, target, predicate=self.predicate)`, tags `match_reason` |
| `spatial_relation/contains_op.py` | `ContainsOp` | `ContainsStep` | `predicate="contains"` |
| `spatial_relation/crosses_op.py` | `CrossesOp` | `CrossesStep` | `predicate="crosses"` |
| `spatial_relation/touches_op.py` | `TouchesOp` | `TouchesStep` | `predicate="touches"` |
| `reference_entity_filter.py` | `ReferenceEntityFilter` (helper, no `@register_op`) | shared | Optional field/operator/value filter on proximity/relation targets |
| `union_find.py` | `UnionFind` (helper) | shared | Deterministic union-find for `cluster.py` |
| `proximity_result_builder.py` | `ProximityResultBuilder` (helper) | shared | Builds `distance_to_target_m`, `match_reason` (Hebrew), `nearest_target_feature` for `near`/`nearest_n` |

## 4. `bl/agent/` — the three LLM-call packages

### `select_layers/` — call 1 (query → relevant catalog layers)

- **`layer_selector.py`** — `LayerSelector(llm, catalog, diet_mode=None)`;
  `select(query) -> LayerSelection`. Loads `prompts/select_layers.md` and
  `select_layers_diet.md` once at construction. Flow:
  `catalog.list_queryable_layers()` (empty → fixed Hebrew clarify) → diet-vs-full
  template picked by `diet_mode()` → `LayerCatalogFormatter` substitutes `{catalog}` →
  `llm.complete_json(system, user=query)` → `LayerSelectionMapper.from_response`.
- **`layer_catalog_formatter.py`** — `LayerCatalogFormatter.format(layers, diet=False)`:
  diet mode `"{id}|{name}|{tags}|{desc}"` (60/6-tags/100-char caps), full mode a longer
  labeled form (80/10-tags/200-char caps). `sanitize(text, limit)` is what bounds
  untrusted catalog text before it reaches the prompt.
- **`layer_selection.py`** — `LayerSelection` (`@dataclass`): `layers`, `clarify`,
  `reasoning`, `token_usage`, `requested_layer_ids` (raw model IDs),
  `dropped_layer_ids` (hallucinated/unknown IDs discarded).
- **`layer_selection_mapper.py`** — `LayerSelectionMapper.from_response(data, layers)`.
  **How hallucinated IDs get dropped:** `_resolve` builds a `by_id` dict from the
  *actual* catalog layers passed in, dedupes the model's `layer_ids`, partitions into
  `picked` (present in `by_id`) vs `dropped` (not present) — dropped IDs never become
  `LayerMeta` objects. Empty `picked` falls back to the model's `clarify` or
  `FALLBACK_CLARIFY`.

### `build_plan/` — call 2 (query + selected schemas → GeoQueryPlan)

- **`plan_builder.py`** — `PlanBuilder(llm, catalog, diet_mode=None)`:
  - `build(query, layers, has_boundaries, now) -> PlanBuildResult` — builds the system
    prompt (`{now}`/`{has_boundaries}`/`{geo_skills}`/`{layers}`), delegates to
    `PlanBuildLoop.run`. `GeoSkillCatalog` combines Pydantic-derived compact operation
    contracts, one provider-neutral routing reference per operation, profiles activated
    by selected-layer typed `profiles`, and a compact custom-skill index. Custom
    `@field[...]` bindings are validated against live schemas and resolved on load.
  - `replan_after_empty(query, layers, previous, has_boundaries, now) ->
    PlanBuildResult` — the zero-result diagnosis path: appends "executed successfully
    but returned zero rows... never widen time, distance, geography, counts, targets,
    or movement thresholds" plus the previous plan JSON, calls `build()` again, then
    runs `preserves_constraints(previous, result.plan)` — on failure, discards the
    revision and returns a fixed clarify.
- **`plan_build_loop.py`** — `PlanBuildLoop` (`_MAX_ATTEMPTS=2`, three
  `sample_field` rounds, two distinct `load_skill` rounds). `run(...)` is the bounded
  LLM/tool/validation loop: each turn either (a) handles a field sample or indexed
  custom-skill load and loops
  again (doesn't count against `_MAX_ATTEMPTS`), (b) accepts a `clarify`, or (c)
  requests the generated plan/tool/clarify JSON Schema when supported, then validates
  via `GeoQueryPlan.model_validate` + `validate_plan` — failure
  appends a correction message and retries up to `_MAX_ATTEMPTS`; exhaustion returns a
  fixed fallback clarify.
- **`plan_build_state.py`** — `PlanBuildState(query)`: `query`, `user`,
  `usage: UsageAccumulator`, `tool_notes`, `tool_calls`, `diagnostics`, `attempt`.
- **`plan_build_result.py`** — `PlanBuildResult` (`@dataclass`): `plan`, `clarify`,
  `attempts`, `token_usage`, `tool_calls`, `diagnostics`.
- **`layer_prompt_formatter.py`** — `LayerPromptFormatter(catalog).format(layers,
  diet=False)` — renders each layer's id/name/geometry type/fields with up to 2 (diet)
  or 5 (full) sample values, pulling live schema via `catalog.get_schema`.
- **`preserves_constraints.py`** — `ConstraintPreserver.preserves(original, revised) ->
  bool` (exposed as `preserves_constraints`). Builds a `(op, tuple of constraint field
  values)` signature per step for a fixed `_CONSTRAINT_FIELDS` table covering
  `attribute_filter`, `near`, `nearest_n`, `near_all`, `between`, `temporal_filter`,
  `cluster`, `movement_direction`, `latest_per_entity`, `within_geometry`. Returns
  `True` only if **every** signature from `original` still exists in `revised` — the
  code-level backstop that rejects removing or widening any of: filters, time,
  geography, distances, counts, targets, netId identity, movement thresholds, during
  zero-result replanning.
- **`usage_accumulator.py`** — `UsageAccumulator.add(usage)` sums token counts across
  build attempts.

### `generate_layer_metadata/` — call 3 (provider sample → catalog description/tags)

- **`layer_metadata_generator.py`** — `LayerMetadataGenerator(llm,
  providers).generate(name, provider_name, source_url, sample_geometry=None) ->
  GeneratedLayerMetadata`. Builds a throwaway preview `LayerMeta`, resolves Cubes
  configurable parameters + whether a sample polygon is required; unresolved params or
  missing required polygon → returns an "unresolved" result without an LLM call.
  Otherwise samples up to `_FETCH_LIMIT=100` features, builds the prompt via
  `MetadataSampleBuilder`, calls `llm.complete_json`, maps via
  `MetadataResponseMapper`.
- **`metadata_sample_builder.py`** — `MetadataSampleBuilder.build(layer, features,
  schema)`. Filters to `metadata_relevant` fields (raises `ProviderError` for an MQS
  layer with none — signals a broken `property_list` mapping), samples up to 10 random
  rows, truncates names/values/field count, serializes a bounded JSON payload.
- **`metadata_response_mapper.py`** — `MetadataResponseMapper.map(...)`. Validates
  non-empty `description`/`tags` (dedup/truncate: `_MAX_TAGS=20`,
  `_MAX_TAG_CHARS=60`, `_MAX_DESCRIPTION_CHARS=2000`); raises `AgentError` if unusable.
- **`generated_layer_metadata.py`** — `GeneratedLayerMetadata` (`@dataclass`):
  `description`, `tags`, `sample_count`, `dynamic_parameters`,
  `configurable_parameters`, `requires_sample_polygon`.

### `bl/agent/prompts/`

```
prompts/
  README.md                   policy doc for prompt tuning + pipeline diagram
  select_layers.md             full call-1 system prompt
  select_layers_diet.md        compact call-1 system prompt
  build_plan.md                 full call-2 system prompt
  build_plan_diet.md            compact call-2 system prompt
  generate_layer_metadata.md   call-3 system prompt (no diet variant)
```
Geo operation selection rules live beside these shells under
`bl/agent/skills/plan-geo-queries/references/`, one reference per operation. The full
prompt gets complete references; diet mode gets their use/avoid lines. Both receive the
same compact operation contracts generated from Pydantic. Conditional domain profiles
live under `profiles/`; custom skill bodies load only after an indexed `load_skill`.

`llm_diet_mode` picks the diet files at runtime via a `diet_mode: Callable[[], bool]`
passed into `LayerSelector`/`PlanBuilder` (default `False` = full prompts when not
supplied). **Diet and full prompts must preserve the same output contracts, operation
set, safety rules, sampling tool, and clarification behavior.** Update shared operation
rules in the skill catalog and profile-specific policy in the prompt shells. Code remains
authoritative for operation shapes/bounds (Pydantic), catalog
ID/filter/reference/boundary/output-order/count validation (`validators.py`), spatial
semantics/CRS (`executor`), and text sanitization/truncation + hallucinated-ID dropping
— prompts only express model behavior/format, never enforce safety by themselves.

## 5. `bl/query_orchestrator/`

- **`query_orchestrator.py`** — `QueryOrchestrator(catalog, executor,
  layer_selector=None, plan_builder=None)`:
  - `run_query(query, boundaries, event_sink=None) -> QueryOutcome` — full
    select→plan→execute→diagnose flow. If selector/builder aren't wired, returns a
    fixed "agent not connected" clarify pointing at `/api/execute-plan`. `_select`
    calls `LayerSelector.select` (short-circuits to clarify). `_build` calls
    `PlanBuilder.build` (short-circuits to clarify). `_execute_query` runs
    `PlanExecutor.execute_detailed`; empty results (`_has_results`) trigger `_handle_empty`
    → `PlanBuilder.replan_after_empty` (the diagnosis step), re-executing once if the
    revision survives `preserves_constraints`. Sums token usage across every LLM stage;
    every stage timed via `StageTimer`, optionally streamed through `event_sink`.
  - `execute_plan(plan, boundaries) -> QueryOutcome` — the "bring your own plan" path
    (`/api/execute-plan`): validates the explicit plan against the live catalog
    (`validate_plan`) and executes directly, skipping both LLM stages.
- **`stage_timer.py`** — `StageTimer.mark(stage)` records elapsed ms since the last
  mark into `self.timing: Dict[str, int]`.
- **`sum_usage.py`** — `UsageAccumulator.sum(*usages)` (exposed as `sum_usage`) — merges
  any number of token-usage dicts, `None` if nothing summed.
- **`query_outcome.py`** — `QueryOutcome` (`@dataclass`): `status` (`"ok"|"clarify"|
  "error"`), `clarify`, `plan`, `features`, `scalar_result` (for count plans),
  `timing_ms`, `token_usage`, `selected_layers`, `reasoning`, `tool_calls`,
  `pipeline_trace` (explicitly user-visible operational trace — **never** private
  model chain-of-thought).

## 6. `bl/catalog/`

- **`catalog_service.py`** — `CatalogService(repository, providers,
  schema_ttl_seconds=3600)`. SRP: resolves layers and schemas; does not execute plans,
  talk HTTP, or know Postgres.
  - `list_layers()`, `list_queryable_layers()` (catalog rows whose provider is
    currently active — `providers.has(...)`), `get_layer(layer_id)` (raises
    `LayerNotFoundError` if missing), `add_layer`, `update_layer_metadata`.
  - `sample_field(layer_id, field, limit=20)` — always live, no cache (the agent's
    on-demand tool).
  - `get_schema(layer_id)` — TTL-cached in-memory (default 1h); on provider failure,
    serves a stale cached copy if one exists, else raises `ProviderError` ("stale beats
    failed").
- **`tyche_activation.py`** — `TycheLayerActivator.activate(repository, provider) ->
  (LayerMeta, created, sample_feature_count)` (exposed as `activate_tyche_layer`).
  Probes the provider with a 1-feature fetch, `upsert_layer`s the canonical "כוחותינו"
  row, preserves operator-added tags, forces the canonical description if blank or
  matches a known `_LEGACY_DESCRIPTIONS` set.
- **`mqs_sync/`**:
  - `remote_mqs_layer.py` — `RemoteMqsLayer` (`@dataclass(frozen=True)`): `id, name,
    description, tags, provider="mqs"`; computed `source_url ->
    f"mqs://layer/{id}"`.
  - `browse_mqs_layers.py` — `MqsLayerBrowser.browse(mqs_provider) -> (layers,
    skipped_count)` (exposed as `browse_mqs_layers`). Normalizes heterogeneous MQS
    entry shapes into `RemoteMqsLayer`s, dedupes by id, truncates fields.
  - `sync_mqs_layers.py` — `MqsLayerSynchronizer.sync(repository, mqs_provider) ->
    MqsSyncResult` (exposed as `sync_mqs_layers`). Browses then `upsert_layer`s each —
    tags only applied on insert, per the repository contract.
  - `mqs_sync_result.py` — `MqsSyncResult` (`@dataclass`): `added=0, updated=0,
    skipped=0`, computed `total`.

## Cross-cutting notes

- **The 18-step Union is the contract surface.** Adding a new plan operation touches:
  the Pydantic model, `step.py`'s Union, `validators.py` (if it needs semantic checks),
  a new `ops/*.py` handler with `@register_op`, `ops/__init__.py`'s import list, one
  `skills/plan-geo-queries/references/*.md` definition, prompt policy when needed,
  `preserves_constraints.py`'s `_CONSTRAINT_FIELDS` (if constraint-bearing), plus
  frontend/tests/docs.
- **Hebrew strings are pervasive** in `match_reason` columns and clarify fallbacks —
  this is a Hebrew-first product.
- **ITM (EPSG:2039)** is the fixed metric CRS for all meter-based spatial math (`near`,
  `near_all`, `nearest_n`, `between`, `cluster`, `movement_direction`,
  `trajectory_relation`, `origin_movement`) via
  `app.common.geo.metric_crs_for`/`to_metric` — WGS84 degrees are never used directly
  for distance math.
- Every op class is effectively a singleton: `OpRegistration.__call__` instantiates the
  handler once at import time and stores that single instance in `_REGISTRY`.
