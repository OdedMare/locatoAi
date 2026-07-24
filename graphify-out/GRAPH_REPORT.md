# Graph Report - .  (2026-07-24)

## Corpus Check
- 354 files · ~95,902 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2523 nodes · 5018 edges · 212 communities (159 shown, 53 thin omitted)
- Extraction: 82% EXTRACTED · 18% INFERRED · 0% AMBIGUOUS · INFERRED: 926 edges (avg confidence: 0.68)
- Token cost: 247,401 input · 0 output

## Community Hubs (Navigation)
- MQS Provider Tests
- Cubes Gateway & Query Builder + Layer Parameter Models
- Agent Skill/Operation Contract Catalog + Skill Field References
- Frontend Agent Studio & Layers Panel (Cubes/Package params)
- Executor Integration Tests
- Layer Selection Pipeline (select_layers agent call)
- Spatial Relation Ops (contains/crosses/touches) + Logging
- FLAPI Client Factory + Cubes Provider Tests
- OpenAI-Compatible LLM Client Chain
- Movement Direction & Trajectory Relation Ops
- DAL Providers (mixed)
- Frontend Dev Dependencies
- Agent Build-Plan Support
- Layers Repository (Postgres catalog CRUD)
- Backend Tests (mixed)
- Backend Tests (mixed)
- Frontend tsconfig
- Backend Tests (mixed)
- Geo-Skill Reference: near
- Catalog Service (layer CRUD orchestration)
- Frontend Components (mixed)
- MQS Entity Mapper
- Latest-Per-Entity & Origin-Movement Prep Ops
- Backend Service Layer (mixed)
- DAL (mixed)
- Agent Build-Plan (plan builder)
- Near-All Executor Op
- Geo-Skill References Index
- FLAPI Provider Package
- Attribute Filter (BL)
- DAL (mixed)
- Backend Tests (mixed)
- Tyche Provider
- Backend Tests (mixed)
- Runtime Settings Tests
- Tyche Provider Tests
- Agent Prompts (build_plan/select_layers)
- Executor Engine (Plan Executor dispatch)
- Backend Tests (mixed)
- Executor Op Base: Execution Context
- Cluster Executor Op
- Backend Common (mixed)
- Agent Layer Metadata Generation
- FLAPI Package Provider
- MQS Entity Stream
- Backend Service (mixed)
- Frontend AGENTS.md
- Executor Op Base: OpHandler Protocol
- Between Executor Op
- DAL (mixed)
- DAL (mixed)
- FLAPI Package Serializer
- Service: Query Router
- Geo-Skill: Plan Build
- FLAPI Packages Provider Tests
- MQS Sync Tests
- Frontend Src (mixed)
- Application State Wiring (composition root)
- Near Executor Op
- Origin-Movement Executor Op
- BL Plan (mixed)
- Backend Common (mixed)
- FLAPI Cube (mixed)
- Backend Service (mixed)
- Frontend Components (mixed)
- MQS Provider (mixed)
- Tyche Gateway
- Backend Service (mixed)
- Frontend Components (mixed)
- Agent Build-Plan: Response Schema & Constraint Preservation
- Provider Protocol (DIP seam)
- FLAPI Providers (mixed)
- Service: Models Router
- Frontend Services (mixed)
- MQS Sync: Browse MQS Layers
- Backend Service (mixed)
- Tyche Provider (core)
- CLAUDE.md: Cubes Catalog Workflow
- Backend Scripts: Eval
- BL: MQS Layer
- Provider Error + Tyche Source
- Tyche Query Builder
- Agent Build-Plan: Layer Prompt Formatter
- Backend Scripts: Eval
- DAL (mixed)
- Backend Service (mixed)
- Backend Service (mixed)
- Service: Catalog Router
- Agent Build-Plan: Geo Skill Catalog
- Attribute Filter Executor Op
- Nearest-N Executor Op
- Runtime Settings Normalizers
- Backend Service (mixed)
- Frontend: Map Results
- FLAPI Cube Parameter Loader
- Backend Service (mixed)
- Service: Feedback
- Text Normalize Tests
- Agent: Metadata Sample Builder
- Count Executor Op + Plan Model
- Directional Executor Op + Plan Model
- Agent Content Tests
- Frontend: MapWorkspace
- Agent BL (mixed)
- Agent BL (mixed)
- BL Catalog: MQS Sync
- Root/Backend/BL CLAUDE.md docs (architecture overview)
- Load Executor Op + Plan Model
- Service: Catalog (mixed)
- Service: Catalog (mixed)
- CLAUDE.md docs (tier index) + Python pin
- Backend Service (mixed)
- Service Shared: GeoDataFrame → FeatureCollection
- Cubes Autocomplete Endpoint Tests
- Attribute Filter Model + Text Normalizer
- Query Request ID Tests
- Query Orchestrator: Usage Summing
- Service: Cubes Autocomplete Request
- Service: MQS Sync Response
- Service: Update Layer Request
- Service: Settings Catalog Status
- Service: Settings Update
- Scripts: Enrich Layer Tags
- Service: Layer Fields Response
- Service: Health Router
- backend/README.md: Settings
- Frontend: App Layout
- Executor Ops Base __init__
- Executor Ops __init__
- Spatial Relation Ops __init__
- Query Orchestrator
- DAL Agent Content __init__
- FLAPI Providers (mixed)
- FLAPI Providers __init__
- Service Agent Config __init__
- Service: Cubes Query Mode
- Service: FLAPI Resource Type
- backend/README.md: Bounded Loading
- backend/README.md: Roadmap
- Frontend: ESLint Config
- Frontend: Next Config
- Frontend: next-env.d.ts
- backend > app > bl > agent > prompts > readme > rules > spli
- backend > app > bl > agent > prompts > readme > tuning > wor
- backend > app > bl > agent > skills > plan > geo > queries >
- backend > app > bl > agent > skills > plan > geo > queries >
- backend > readme > lifecycle > stages
- backend > readme > ntier > solid
- backend > readme > running > section
- backend > readme > service > routes > table
- backend > readme > solid > mapping
- backend > readme > tests > section
- bl > agent > prompts > dir
- bl > cross > cutting > notes
- bl > dip > seam > protocols
- bl > layer > field > model
- bl > layer > meta > model
- bl > layer > parameter > model
- bl > layer > parameter > option > model
- bl > layer > schema > model
- claude > md > frontend > architecture
- claude > md > gotchas
- claude > md > map > specifics
- pkg > ailocator > backend
- readme > cubes > section
- readme > flow > packages > section
- readme > llm > provider > section
- readme > mqs > section
- readme > postgresql > section
- readme > system > at > a > glance

## God Nodes (most connected - your core abstractions)
1. `LayerMeta` - 147 edges
2. `ProviderError` - 114 edges
3. `RuntimeSettingsStore` - 60 edges
4. `make_provider()` - 55 edges
5. `ExecutionContext` - 50 edges
6. `mqs_layer()` - 50 edges
7. `QueryOrchestrator` - 43 edges
8. `CatalogRouter` - 42 edges
9. `PlanBuilder` - 41 edges
10. `LayerSchema` - 41 edges

## Surprising Connections (you probably didn't know these)
- `types/geo-query.ts` --shares_data_with--> `QueryRequest`  [INFERRED]
  frontend/README.md → backend/app/service/query/request.py
- `latest_per_entity operation` --semantically_similar_to--> `AppShell`  [INFERRED] [semantically similar]
  backend/app/bl/agent/skills/plan-geo-queries/references/08-latest-per-entity.md → frontend/README.md
- `{query, boundaries} wire contract` --shares_data_with--> `QueryRequest`  [EXTRACTED]
  frontend/README.md → backend/app/service/query/request.py
- `Agent loop constraints` --semantically_similar_to--> `Bounded agent loop description`  [INFERRED] [semantically similar]
  CLAUDE.md → backend/README.md
- `Settings precedence (env vs runtime overrides)` --semantically_similar_to--> `Settings model (two-layer store)`  [INFERRED] [semantically similar]
  CLAUDE.md → backend/README.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Self-registering executor op handlers implementing OpHandler via @register_op** — bl_op_handler, bl_op_registry, bl_op_registration, bl_load_op, bl_within_geometry_op, bl_attribute_filter_op, bl_near_op, bl_near_all_op, bl_nearest_n_op, bl_directional_op, bl_movement_direction_op, bl_trajectory_relation_op, bl_origin_movement_op, bl_latest_per_entity_op, bl_cluster_op, bl_count_op, bl_between_op, bl_temporal_filter_op, bl_spatial_relation_op_base [EXTRACTED 1.00]
- **The 18 GeoQueryPlan step models composing the discriminated Step Union** — bl_step_union, bl_load_step, bl_within_geometry_step, bl_attribute_filter_step, bl_near_step, bl_nearest_n_step, bl_near_all_step, bl_between_step, bl_crosses_step, bl_touches_step, bl_contains_step, bl_directional_step, bl_temporal_filter_step, bl_cluster_step, bl_latest_per_entity_step, bl_movement_direction_step, bl_trajectory_relation_step, bl_origin_movement_step, bl_count_step [EXTRACTED 1.00]
- **Three-LLM-call agent pipeline: select layers, build plan, generate layer metadata, orchestrated end-to-end** — bl_layer_selector, bl_plan_builder, bl_layer_metadata_generator, bl_query_orchestrator, backend_app_bl_agent_prompts_select_layers_md, backend_app_bl_agent_prompts_build_plan_md, backend_app_bl_agent_prompts_generate_layer_metadata_md [INFERRED 0.90]
- **FLAPI Cube resource fetch pipeline** — backend_app_dal_providers_flapi_cube_source_cubessource, backend_app_dal_providers_flapi_client_factory_flapiclientfactory, backend_app_dal_providers_flapi_cube_metadata_gateway_cubesmetadatagateway, backend_app_dal_providers_flapi_cube_query_builder_cubesquerybuilder, backend_app_dal_providers_flapi_cube_gateway_cubesgateway, backend_app_dal_providers_flapi_schema_mapper_flapischemamapper, backend_app_dal_providers_flapi_cube_provider_cubesprovider [EXTRACTED 1.00]
- **Provider protocol implementations (MQS, Cubes, Tyche)** — backend_app_dal_claude_provider_protocol, backend_app_dal_providers_mqs_provider_mqsprovider, backend_app_dal_providers_flapi_cube_provider_cubesprovider, backend_app_dal_providers_tyche_provider_tycheprovider [EXTRACTED 1.00]
- **Moving-entity plan operations relying on schema entity/time roles** — backend_app_bl_agent_skills_plan_geo_queries_references_08_latest_per_entity_latest_per_entity, backend_app_bl_agent_skills_plan_geo_queries_references_09_movement_direction_movement_direction, backend_app_bl_agent_skills_plan_geo_queries_references_17_trajectory_relation_trajectory_relation, backend_app_bl_agent_skills_plan_geo_queries_references_18_origin_movement_origin_movement, backend_app_bl_agent_skills_plan_geo_queries_references_entity_time_schema_roles [INFERRED 0.85]

## Communities (212 total, 53 thin omitted)

### Community 0 - "MQS Provider Tests"
Cohesion: 0.07
Nodes (78): entity(), make_provider(), make_store(), mqs_layer(), Request, Response, The doc's paginated shape: {"entities_list": [...], "next_page": null}., The doc's first (non-paginated) section shows a bare JSON array —     still acce (+70 more)

### Community 1 - "Cubes Gateway & Query Builder + Layer Parameter Models"
Cohesion: 0.06
Nodes (23): LayerParameter, LayerParameterOption, BaseModel, One selectable catalog parameter value., One selectable value for a dynamic (autocomplete-backed) parameter., BaseModel, Provider parameter metadata exposed through the catalog., CubesGateway (+15 more)

### Community 2 - "Agent Skill/Operation Contract Catalog + Skill Field References"
Cohesion: 0.05
Nodes (19): Path, OperationContractCatalog, Render compact operation contracts from the authoritative Pydantic models., Resolve stable layer-field references embedded by Agent Studio., SkillFieldReferences, AgentContentRepository, Path, File-backed defaults with runtime-persisted agent content overrides. (+11 more)

### Community 3 - "Frontend Agent Studio & Layers Panel (Cubes/Package params)"
Cohesion: 0.07
Nodes (53): AgentStudioPanel(), AgentStudioPanelProps, AREA_SUMMARY_EXAMPLES, friendlyError(), itemKey(), kindLabel(), CubesParameterOptionPickerProps, CubesParametersFieldsetProps (+45 more)

### Community 4 - "Executor Integration Tests"
Cohesion: 0.05
Nodes (60): load_fixture_plan(), load must forward the request's user_geometry to the provider as a     pushdown, No boundaries on the request → load must not invent a geometry filter., near needs only targets inside the request boundary plus distance., Every layer load must carry the request polygon to its provider., חולון schools (שרת/קציר) are ~400m apart, isolated from the rest of     the laye, The two-member Holon group is excluded when three are required;     independent, A radius wide enough to also pull in the central-Tel-Aviv schools     as their o (+52 more)

### Community 5 - "Layer Selection Pipeline (select_layers agent call)"
Cohesion: 0.05
Nodes (28): LayerCatalogFormatter, Render sanitized catalog metadata for layer selection., LayerSelectionMapper, Map raw LLM layer-selection JSON into the domain result., LayerSelector, Select query-relevant layers from sanitized catalog metadata., AgentRouter, Request (+20 more)

### Community 6 - "Spatial Relation Ops (contains/crosses/touches) + Logging"
Cohesion: 0.05
Nodes (31): ContainsOp, CrossesOp, GeoDataFrame, SpatialRelationOp, TouchesOp, ContainsStep, CrossesStep, BaseModel (+23 more)

### Community 7 - "FLAPI Client Factory + Cubes Provider Tests"
Cohesion: 0.11
Nodes (49): FlapiClientFactory, BaseTransport, Client, Create authenticated FLAPI HTTP clients., layer(), make_provider(), posted_request(), Request (+41 more)

### Community 8 - "OpenAI-Compatible LLM Client Chain"
Cohesion: 0.06
Nodes (28): AgentError, The LLM call failed (missing key, network, unparseable output)., LLMClient protocol, CompletionRetry, Bounded retry for transient OpenAI-compatible failures., LLM completion degradation ladder (schema -> json mode -> plain -> merged system), JsonResponseParser, Extract a JSON object from an LLM response. (+20 more)

### Community 9 - "Movement Direction & Trajectory Relation Ops"
Cohesion: 0.07
Nodes (23): MovementDirectionOp, GeoDataFrame, GeoDataFrame, TrajectoryRelationOp, MovementDirectionStep, BaseModel, BaseModel, TrajectoryRelationStep (+15 more)

### Community 10 - "DAL Providers (mixed)"
Cohesion: 0.08
Nodes (13): LayerField, BaseModel, Queryable field metadata for a catalog layer., A few distinct example values — lets the plan agent write attribute     filters, LayerSchema, BaseModel, Schema of a layer as reported by its provider (fetched on demand)., FlapiSchemaMapper (+5 more)

### Community 11 - "Frontend Dev Dependencies"
Cohesion: 0.04
Nodes (44): eslint, eslint-config-next, dependencies, leaflet, leaflet-draw, lucide-react, next, react (+36 more)

### Community 12 - "Agent Build-Plan Support"
Cohesion: 0.16
Nodes (10): PlanBuildResult, LayerSelection, ExecutionOutput, Executor result; scalar aggregations do not retain feature rows., Any, BaseGeometry, datetime, QueryOrchestrator (+2 more)

### Community 13 - "Layers Repository (Postgres catalog CRUD)"
Cohesion: 0.09
Nodes (14): LayersRepository, Protocol, LayerMeta, BaseModel, Business metadata for one catalog layer., Keep old tag-backed catalogs readable while the core stays typed., Encode typed semantics only at the legacy Postgres boundary., One row of the catalog (public.layers). Metadata only — never features. (+6 more)

### Community 14 - "Backend Tests (mixed)"
Cohesion: 0.14
Nodes (20): PlanBuilder, datetime, Build and revise validated geographic query plans., LLMClient fake returning queued responses; records prompts., SequenceLLM, test_builder_clarify_passthrough(), test_diet_plan_prompt_is_short_and_preserves_all_operations(), test_hebrew_multi_reference_query_builds_near_all() (+12 more)

### Community 15 - "Backend Tests (mixed)"
Cohesion: 0.11
Nodes (18): FakeLayersRepository, In-memory implementation of the LayersRepository port., make_app(), FastAPI, test_create_layer_persists_declared_entity_role_as_metadata(), test_delete_layer_removes_it_from_the_catalog(), test_delete_unknown_layer_returns_404(), test_edit_layer_updates_metadata_but_preserves_source_identity() (+10 more)

### Community 16 - "Frontend tsconfig"
Cohesion: 0.06
Nodes (30): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+22 more)

### Community 17 - "Backend Tests (mixed)"
Cohesion: 0.15
Nodes (28): PlanValidationError, The plan is structurally invalid (bad refs, cycles, unknown layers...)., make_plan(), test_between_plan_parses(), test_boundaries_require_within_geometry_step(), test_count_as_output_with_nothing_downstream_is_valid(), test_count_not_set_as_output_rejected(), test_count_referenced_as_input_rejected() (+20 more)

### Community 18 - "Geo-Skill Reference: near"
Cohesion: 0.10
Nodes (28): plan-geo-queries SKILL, 18-op description table, AttributeFilterStep (op=attribute_filter), BetweenStep (op=between), ClusterStep (op=cluster), ContainsStep (op=contains), CountStep (op=count), CrossesStep (op=crosses) (+20 more)

### Community 19 - "Catalog Service (layer CRUD orchestration)"
Cohesion: 0.10
Nodes (8): CatalogService, Persist a new catalog layer through the repository port., ProviderRegistry, Protocol, Resolves a catalog `provider` name to a Provider instance., LayerNotFoundError, test_queryable_layers_exclude_unregistered_legacy_providers(), test_selector_clarifies_without_calling_llm_when_no_provider_is_active()

### Community 20 - "Frontend Components (mixed)"
Cohesion: 0.15
Nodes (20): RFC-7946, GeographyControlsProps, MODES, DRAW_HINTS, LeafletMap, MapWorkspace(), MapWorkspaceProps, toDms() (+12 more)

### Community 21 - "MQS Entity Mapper"
Cohesion: 0.16
Nodes (4): MqsEntityMapper, BaseGeometry, GeoDataFrame, Normalize MQS entities into schemas and GeoDataFrames.

### Community 22 - "Latest-Per-Entity & Origin-Movement Prep Ops"
Cohesion: 0.11
Nodes (13): LatestPerEntityOp, GeoDataFrame, Shared optional filtering for proximity reference layers., ReferenceEntityFilter, GeoDataFrame, TemporalFilterOp, LatestPerEntityStep, BaseModel (+5 more)

### Community 23 - "Backend Service Layer (mixed)"
Cohesion: 0.13
Nodes (10): The layers table as a safely quoted SQL identifier., The feedback table as a safely quoted SQL identifier., RuntimeSettings, BaseModel, SettingsResponse, Request, GET/PUT /api/settings with write-only secret handling., SettingsRouter (+2 more)

### Community 24 - "DAL (mixed)"
Cohesion: 0.17
Nodes (6): _AttributeFilters, MqsGateway, BaseGeometry, Client, MQS HTTP boundary and basic pagination., HTTPStatusError

### Community 25 - "Agent Build-Plan (plan builder)"
Cohesion: 0.14
Nodes (6): PlanBuildLoop, Bounded LLM/tool/validation loop for plan construction., PlanBuildState, Mutable state for one bounded plan-building conversation., Sums token usage across build attempts., UsageAccumulator

### Community 26 - "Near-All Executor Op"
Cohesion: 0.14
Nodes (12): NearAllOp, GeoDataFrame, Proximity to every reference in a multi-layer relationship query., Require proximity to ALL targets, then optionally rank and limit.      Ranking u, NearAllStep, BaseModel, ProximityTarget, BaseModel (+4 more)

### Community 27 - "Geo-Skill References Index"
Cohesion: 0.15
Nodes (23): latest_per_entity operation, movement_direction operation, directional operation, between operation, crosses operation, touches operation, contains operation, temporal_filter operation (+15 more)

### Community 28 - "FLAPI Provider Package"
Cohesion: 0.12
Nodes (6): FlowPackageGateway, Response, Flow Package metadata and execution HTTP boundary., FlapiSource, Any, Parse FLAPI resource URLs and persisted package inputs.

### Community 29 - "Attribute Filter (BL)"
Cohesion: 0.09
Nodes (23): AttributeFilterOp, BetweenOp, ClusterOp, ContainsOp, CountOp, CrossesOp, DirectionalOp, LatestPerEntityOp (+15 more)

### Community 30 - "DAL (mixed)"
Cohesion: 0.15
Nodes (9): LayerMeta, PostgresLayersRepository, Postgres-backed catalog repository.  Implements the bl.ports.LayersRepository pr, Insert or update keyed on (provider, source_url) — the stable         identity o, LayersRepository protocol, PostgresConnection, PostgreSQL connection factory driven by live runtime settings., enrich_layer_tags.py bilingual tag enrichment run (+1 more)

### Community 31 - "Backend Tests (mixed)"
Cohesion: 0.22
Nodes (15): ProviderRegistry protocol, InMemoryProviderRegistry, Provider registry: catalog `provider` name → adapter instance.  OCP: registering, CapturingLlm, test_cubes_metadata_discovers_dynamic_parameter_before_row_fetch(), test_cubes_metadata_discovers_required_parameter_details_before_row_fetch(), test_cubes_metadata_exposes_snake_case_required_parameter_before_row_fetch(), test_cubes_metadata_samples_main_route_after_dynamic_value_is_resolved() (+7 more)

### Community 32 - "Tyche Provider"
Cohesion: 0.19
Nodes (5): BaseGeometry, GeoDataFrame, Map Tyche rows to geographic features., TycheFeatureMapper, BaseTransport

### Community 33 - "Backend Tests (mixed)"
Cohesion: 0.15
Nodes (12): catalog(), executor(), frozen_now(), providers(), datetime, Accident timestamps are generated relative to now — freeze it., MockGisProvider, BaseGeometry (+4 more)

### Community 34 - "Runtime Settings Tests"
Cohesion: 0.18
Nodes (21): make_store(), test_bad_saved_database_url_skipped_on_startup(), test_cubes_settings_normalize_persist_and_clear(), test_env_defaults_apply(), test_jdbc_database_url_is_normalized(), test_llm_base_url_can_be_cleared(), test_llm_base_url_normalization(), test_llm_base_url_requires_scheme() (+13 more)

### Community 35 - "Tyche Provider Tests"
Cohesion: 0.27
Nodes (19): layer(), make_provider(), Request, Response, record(), RecordingHandler, request_body(), test_custom_layer_uses_its_route_and_field_mapping() (+11 more)

### Community 36 - "Agent Prompts (build_plan/select_layers)"
Cohesion: 0.14
Nodes (21): build_plan_diet.md (compact call-2 system prompt), load_skill tool contract, build_plan.md (full call-2 system prompt), Agent prompts README, Pipeline position diagram, select_layers_diet.md (compact call-1 system prompt), select_layers.md (full call-1 system prompt), The agent (call 1 / call 2 / sample_field / diet mode / Agent Studio) (+13 more)

### Community 37 - "Executor Engine (Plan Executor dispatch)"
Cohesion: 0.19
Nodes (8): PlanExecutor, Any, BaseGeometry, datetime, Exception, GeoDataFrame, Plan execution engine.  Runs steps in list order — validators guarantee every `i, Run a validated plan and return the output step's result.          A GeoDataFram

### Community 38 - "Backend Tests (mixed)"
Cohesion: 0.11
Nodes (11): Cached environment-settings provider., SettingsProvider, Application configuration (env-driven)., Env-derived DEFAULTS. Values the user can edit in the UI live in     common.runt, Settings, GenerateLayerMetadataRequest, CapturingMetadataGenerator, MqsMetadataProvider (+3 more)

### Community 39 - "Executor Op Base: Execution Context"
Cohesion: 0.15
Nodes (10): ExecutionContext, BaseGeometry, GeoDataFrame, Everything ops may need. Engine-owned, passed to every op., GeoDataFrame, WithinGeometryOp, A provider returning features in a metric CRS must still intersect     correctly, Two loads of the same layer+geometry with different eq-filter values     must no (+2 more)

### Community 40 - "Cluster Executor Op"
Cohesion: 0.15
Nodes (8): ClusterOp, GeoDataFrame, Keep features that belong to a group of >= min_group_size input     rows all mut, Deterministic union-find used by spatial clustering., UnionFind, ClusterStep, BaseModel, Find groups of >= min_group_size input features all mutually within     max_dist

### Community 41 - "Backend Common (mixed)"
Cohesion: 0.20
Nodes (8): GeoUtils, BaseGeometry, GeoDataFrame, Shared CRS helpers for safe spatial calculations., test_buffer_wgs84_geometry_expands_in_meters(), test_metric_crs_is_estimated_for_data_location_not_fixed_to_israel(), CRS, GeoSeries

### Community 42 - "Agent Layer Metadata Generation"
Cohesion: 0.19
Nodes (5): GeneratedLayerMetadata, LayerMetadataGenerator, Generate editable catalog metadata from a bounded provider sample., MetadataResponseMapper, Validate and bound LLM-generated catalog metadata.

### Community 43 - "FLAPI Package Provider"
Cohesion: 0.22
Nodes (5): FlowPackageProvider, BaseGeometry, datetime, GeoDataFrame, Flow Package provider orchestration.

### Community 44 - "MQS Entity Stream"
Cohesion: 0.21
Nodes (4): MqsEntityStream, BaseGeometry, Client, Stream, split, deduplicate, and enrich MQS entities.

### Community 45 - "Backend Service (mixed)"
Cohesion: 0.17
Nodes (7): Request, CatalogLayer, CreateLayerRequest, LayerFieldsResponse, LayersResponse, MqsSyncResponse, UpdateLayerRequest

### Community 46 - "Frontend AGENTS.md"
Cohesion: 0.13
Nodes (18): Next.js 16 breaking-changes warning, Frontend development context (CLAUDE.md), {query, boundaries} wire contract, AgentStudioPanel, AppShell, GeographyControls, GeoQueryInput, LayerPicker (+10 more)

### Community 47 - "Executor Op Base: OpHandler Protocol"
Cohesion: 0.16
Nodes (9): ABC, OpHandler, GeoDataFrame, One handler per plan op., A GeoDataFrame for every op except a terminal `count` step,         which return, OpRegistration, Callable registration decorator for one executor operation., OpRegistry (+1 more)

### Community 48 - "Between Executor Op"
Cohesion: 0.18
Nodes (8): BetweenOp, GeoDataFrame, Select features in a configurable corridor between two references., Keep input geometries intersecting corridors between reference pairs., BetweenStep, BaseModel, Both reference layers must be fetched using a geometry hint buffered     by corr, test_between_buffers_target_fetches_by_corridor_width()

### Community 49 - "DAL (mixed)"
Cohesion: 0.17
Nodes (7): Provider protocol, MqsProvider, BaseGeometry, datetime, GeoDataFrame, MQS provider orchestration.  Entity parsing, filter construction, pagination, sp, Fetch one MQS sample and build its schema from the same entities.          Metad

### Community 50 - "DAL (mixed)"
Cohesion: 0.22
Nodes (4): FlowPackageMetadata, Any, Normalize Flow Package parameter metadata., test_package_validates_absolute_time_and_unknown_types()

### Community 51 - "FLAPI Package Serializer"
Cohesion: 0.26
Nodes (4): FlowPackageSerializer, Any, BaseGeometry, Serialize and validate Flow Package inputs.

### Community 52 - "Service: Query Router"
Cohesion: 0.19
Nodes (5): QueryEventSink, Event sink for one query request., Request, QueryRouter, POST /api/query — natural-language query entry point.

### Community 53 - "Geo-Skill: Plan Build"
Cohesion: 0.12
Nodes (17): GeoQueryPlan JSON example, ExecutionContext (@dataclass), ExecutionOutput (@dataclass), GeoQueryPlan(BaseModel), OpRegistration (@register_op decorator), OpRegistry / register_op / get_op_handler, PlanBuildLoop, PlanBuildState (+9 more)

### Community 54 - "FLAPI Packages Provider Tests"
Cohesion: 0.24
Nodes (14): configured_source(), definitions(), make_provider(), package_layer(), PackageHandler, Request, Response, test_flapi_package_discovers_serializes_executes_and_maps_rows() (+6 more)

### Community 55 - "MQS Sync Tests"
Cohesion: 0.22
Nodes (13): FakeMqsProvider, make_app(), FastAPI, test_browse_endpoint_does_not_insert(), test_browse_endpoint_unknown_provider_payload_is_502(), test_browse_normalizes_without_inserting(), test_browse_uses_mqs_display_name(), test_entry_without_id_is_skipped() (+5 more)

### Community 56 - "Frontend Src (mixed)"
Cohesion: 0.20
Nodes (10): GeoQueryInput(), GeoQueryInputProps, QueryPanelProps, RequestPreviewProps, formatValue(), INTERNAL_FIELDS, ResultsPanelProps, ResultsTable() (+2 more)

### Community 57 - "Application State Wiring (composition root)"
Cohesion: 0.18
Nodes (7): ApplicationStateWiring, Build and assign the application's dependency graph., ApplicationFactory, FastAPI, Application composition root., ErrorHandlerRegistry, Register domain-to-HTTP error mappings.

### Community 58 - "Near Executor Op"
Cohesion: 0.17
Nodes (7): NearOp, GeoDataFrame, Keep input features within distance_m of ANY target-layer feature.      Locked d, ProximityResultBuilder, Build enriched result rows for proximity operations., NearStep, BaseModel

### Community 59 - "Origin-Movement Executor Op"
Cohesion: 0.23
Nodes (4): OriginMovementOp, GeoDataFrame, OriginMovementStep, BaseModel

### Community 60 - "BL Plan (mixed)"
Cohesion: 0.26
Nodes (4): BaseModel, WithinGeometryStep, PlanValidator, Semantic validation for parsed geographic query plans.

### Community 61 - "Backend Common (mixed)"
Cohesion: 0.16
Nodes (5): Settings precedence (runtime-settings.json > env vars > dataclass defaults), Apply a partial update, validate, and persist., RuntimeSettingsStore, FakeConnection, test_feedback_is_inserted_in_configured_postgres_table()

### Community 62 - "FLAPI Cube (mixed)"
Cohesion: 0.16
Nodes (4): CubesMetadataGateway, Cubes metadata, parameter-definition, and autocomplete HTTP access., CubesSource, Parse Cubes catalog source URLs.

### Community 63 - "Backend Service (mixed)"
Cohesion: 0.14
Nodes (10): ExecutePlanRequest, BaseModel, Debug endpoint input: a hand-written plan (no AI involved)., PlanRouter, Request, POST /api/execute-plan — debug endpoint: run a hand-written plan.  Plan-in → Geo, GeoJSONMultiPolygon, BaseGeometry (+2 more)

### Community 64 - "Frontend Components (mixed)"
Cohesion: 0.15
Nodes (13): AgentTrace, AgentTrace(), AgentTraceProps, describeStep(), EXTREME_DIRECTION_HE, MOVEMENT_DIRECTION_HE, OP_HE, ORIGIN_MOVEMENT_HE (+5 more)

### Community 65 - "MQS Provider (mixed)"
Cohesion: 0.19
Nodes (5): MqsFilterBuilder, BaseGeometry, Build MQS filters and split dense geographic regions., BaseTransport, BaseTransport

### Community 66 - "Tyche Gateway"
Cohesion: 0.25
Nodes (3): Client, HTTP and pagination boundary for Tyche., TycheGateway

### Community 67 - "Backend Service (mixed)"
Cohesion: 0.14
Nodes (12): Service tier API endpoint table, get_orchestrator(), Request, FastAPI accessors for dependencies wired on app.state., plan/router.py, BaseModel, QueryRequest, The contract with the frontend: exactly {query, boundaries}. (+4 more)

### Community 68 - "Frontend Components (mixed)"
Cohesion: 0.24
Nodes (12): SettingsPanel, fetchModels(), SETTINGS_SECTIONS, SettingsPanel(), SettingsPanelProps, SettingsSection, getModels(), getSettings() (+4 more)

### Community 69 - "Agent Build-Plan: Response Schema & Constraint Preservation"
Cohesion: 0.20
Nodes (7): PlanResponseSchema, JSON Schema for every valid plan-builder response shape., ConstraintPreserver, GeoQueryPlan, BaseModel, test_detailed_count_releases_the_counted_geometries(), test_empty_plan_rejected()

### Community 70 - "Provider Protocol (DIP seam)"
Cohesion: 0.15
Nodes (8): Provider, BaseGeometry, datetime, GeoDataFrame, Protocol, A GIS data provider (implemented by dal.providers.*).      ISP: this is intentio, geometry, when given, is a WGS84 hint the provider MAY push down         as a se, Distinct example values of one field — backs the plan agent's         on-demand

### Community 71 - "FLAPI Providers (mixed)"
Cohesion: 0.22
Nodes (5): FlapiSource, FlowPackageProvider, FlowPackageSerializer, FlapiProvider, Top-level FLAPI provider dispatching Cube and Flow Package resources.

### Community 72 - "Service: Models Router"
Cohesion: 0.20
Nodes (9): ModelsProbeRequest, BaseModel, Unsaved LLM connection settings used to probe models., ModelsResponse, BaseModel, Available LLM model identifiers., ModelsRouter, Request (+1 more)

### Community 73 - "Frontend Services (mixed)"
Cohesion: 0.23
Nodes (10): next.config.ts /api/:path* rewrite, AppShell(), INITIAL_VIEW, errorDetail(), failedResponse(), submitQuery(), transportFailure(), bboxToMultiPolygon() (+2 more)

### Community 74 - "MQS Sync: Browse MQS Layers"
Cohesion: 0.28
Nodes (3): MqsLayerBrowser, RemoteMqsLayer, RemoteMqsLayer

### Community 75 - "Backend Service (mixed)"
Cohesion: 0.21
Nodes (8): QueryOutcome, BaseModel, QueryResponse, BaseModel, Selected layer included in a query response., Agent trace: one layer the model chose (for the UI's agent panel)., SelectedLayerDto, test_count_response_omits_redundant_feature_collection()

### Community 76 - "Tyche Provider (core)"
Cohesion: 0.27
Nodes (6): BaseGeometry, BaseTransport, datetime, GeoDataFrame, Tyche provider orchestration.  Request construction, transport, feature mapping,, TycheProvider

### Community 77 - "CLAUDE.md: Cubes Catalog Workflow"
Cohesion: 0.21
Nodes (13): CubesProvider description, FLAPI provider (top-level dispatcher), Flow Packages provider description, MQS provider description, Providers section (mqs/flapi/cubes/tyche/flow-packages), Tyche provider description, Provider(Protocol), Cubes catalog workflow (+5 more)

### Community 78 - "Backend Scripts: Eval"
Cohesion: 0.27
Nodes (12): _catalog(), _check_fields(), _check_ops(), check_plan(), _check_roles(), main(), _names(), Scored live eval for GeoQueryPlan operation selection.  The cases provide real c (+4 more)

### Community 79 - "BL: MQS Layer"
Cohesion: 0.17
Nodes (12): sample_field tool contract, Catalog sync (MQS layer upsert), CatalogService, InMemoryProviderRegistry (impl), LayersRepository(Protocol), MqsLayerBrowser / browse_mqs_layers, MqsLayerSynchronizer / sync_mqs_layers, MqsSyncResult (@dataclass) (+4 more)

### Community 80 - "Provider Error + Tyche Source"
Cohesion: 0.30
Nodes (4): ProviderError, A provider failed to serve schema or features., Parse a catalog Tyche source into its route and field mapping., TycheSource

### Community 81 - "Tyche Query Builder"
Cohesion: 0.39
Nodes (4): BaseGeometry, datetime, Build Tyche requests., TycheQueryBuilder

### Community 83 - "Backend Scripts: Eval"
Cohesion: 0.22
Nodes (5): Live accessor for the agent's diet-mode setting., RuntimeDietMode, main(), Live provider-neutral planning eval with synthetic layer schemas.  Runs without, SyntheticCatalog

### Community 84 - "DAL (mixed)"
Cohesion: 0.22
Nodes (7): PostgresFeedbackRepository, datetime, PostgreSQL persistence for user feedback., feedback/router.py, check(), main(), Scored eval: canned queries (Hebrew + English) through layer selection against t

### Community 85 - "Backend Service (mixed)"
Cohesion: 0.18
Nodes (7): CubesAutocompleteOptionResponse, BaseModel, Cubes autocomplete option response., CubesAutocompleteResponse, BaseModel, CubesAutocompleteRequest, CubesAutocompleteResponse

### Community 86 - "Backend Service (mixed)"
Cohesion: 0.20
Nodes (7): FlapiParameterResponse, BaseModel, FLAPI resource parameter response., GeneratedLayerMetadataResponse, BaseModel, GeneratedLayerMetadataResponse, GenerateLayerMetadataRequest

### Community 87 - "Service: Catalog Router"
Cohesion: 0.31
Nodes (3): CatalogRouter, Any, Layer-catalog HTTP controller.

### Community 88 - "Agent Build-Plan: Geo Skill Catalog"
Cohesion: 0.31
Nodes (3): GeoSkillCatalog, Load model-facing GeoQueryPlan operation skills., test_geo_skill_catalog_documents_and_renders_every_operation()

### Community 89 - "Attribute Filter Executor Op"
Cohesion: 0.29
Nodes (4): AttributeFilterOp, GeoDataFrame, AttributeFilterStep, BaseModel

### Community 90 - "Nearest-N Executor Op"
Cohesion: 0.29
Nodes (5): NearestNOp, GeoDataFrame, Keep the `count` input features globally closest to ANY target-layer     feature, NearestNStep, BaseModel

### Community 92 - "Backend Service (mixed)"
Cohesion: 0.20
Nodes (6): BaseModel, Remote MQS layer response., RemoteMqsLayerResponse, BaseModel, RemoteMqsLayersResponse, RemoteMqsLayersResponse

### Community 93 - "Frontend: Map Results"
Cohesion: 0.27
Nodes (9): centerOf(), INTERNAL_PROPERTIES, MapResults(), MapResultsProps, MOVEMENT_STYLE, POINT_STYLE, popupContent(), SHAPE_STYLE (+1 more)

### Community 95 - "Backend Service (mixed)"
Cohesion: 0.28
Nodes (4): ErrorHandler, Exception, FastAPI exception handler with structured diagnostics., JSONResponse

### Community 96 - "Service: Feedback"
Cohesion: 0.25
Nodes (6): FeedbackRequest, BaseModel, Agent-selection feedback request., FeedbackRouter, Request, POST /api/feedback — user verdicts on agent selections.  Stores feedback in the

### Community 99 - "Count Executor Op + Plan Model"
Cohesion: 0.29
Nodes (5): CountOp, Terminal aggregation: row count of the upstream step's result.      No grouping/, CountStep, BaseModel, Terminal aggregation: row count of the upstream step, as a plain     int. No gro

### Community 100 - "Directional Executor Op + Plan Model"
Cohesion: 0.29
Nodes (5): DirectionalOp, GeoDataFrame, Take the `count` most-northern/southern/eastern/western features., DirectionalStep, BaseModel

### Community 101 - "Agent Content Tests"
Cohesion: 0.46
Nodes (7): make_repository(), test_agent_config_api_lists_edits_and_creates_content(), test_agent_config_rejects_stale_skill_field_reference(), test_custom_skill_is_indexed_and_loaded_on_demand(), test_domain_profile_is_rendered_only_when_activated(), test_plan_loop_loads_custom_skill_before_planning(), test_prompt_edits_persist_and_required_placeholders_are_protected()

### Community 102 - "Frontend: MapWorkspace"
Cohesion: 0.36
Nodes (5): LayerOption, LAYERS, LayerPicker(), LayerPickerProps, MapLayers()

### Community 103 - "Agent BL (mixed)"
Cohesion: 0.29
Nodes (3): LLMClient, Protocol, JSON-mode LLM completion implemented by the DAL LLM context.      Returns the pa

### Community 104 - "Agent BL (mixed)"
Cohesion: 0.29
Nodes (7): generate_layer_metadata.md (call-3 system prompt), GeneratedLayerMetadata (@dataclass), LayerMetadataGenerator, LLMClient(Protocol), MetadataResponseMapper, MetadataSampleBuilder, OpenAIJsonClient (impl)

### Community 106 - "Root/Backend/BL CLAUDE.md docs (architecture overview)"
Cohesion: 0.29
Nodes (7): app/bl/ CLAUDE.md (Business Logic Tier), Backend CLAUDE.md (navigation entry point), AiLocator Backend README, Backend architecture (N-tier + SOLID), LocatoAI Project (root CLAUDE.md), Locked decisions (MVP guide), LocatoAI README (system overview)

### Community 107 - "Load Executor Op + Plan Model"
Cohesion: 0.33
Nodes (4): LoadOp, GeoDataFrame, LoadStep, BaseModel

### Community 108 - "Service: Catalog (mixed)"
Cohesion: 0.29
Nodes (5): CatalogLayer, BaseModel, Catalog layer response., LayersResponse, BaseModel

### Community 109 - "Service: Catalog (mixed)"
Cohesion: 0.29
Nodes (4): CreateLayerRequest, CubesParameterValues, BaseModel, Resolved Cubes parameter values.

### Community 110 - "CLAUDE.md docs (tier index) + Python pin"
Cohesion: 0.33
Nodes (6): app/bl/CLAUDE.md, app/common/CLAUDE.md, app/dal/CLAUDE.md, Backend tier documentation index, app/service/CLAUDE.md, Python 3.8.10 runtime pin

### Community 111 - "Backend Service (mixed)"
Cohesion: 0.33
Nodes (6): catalog/router.py, settings/router.py, Settings secrets masking rules, Zero-logic router compliance and its two exceptions, types/catalog.ts, types/settings.ts

### Community 112 - "Service Shared: GeoDataFrame → FeatureCollection"
Cohesion: 0.33
Nodes (4): FeatureCollectionMapper, Any, GeoDataFrame, GeoDataFrame-to-GeoJSON translation.

### Community 113 - "Cubes Autocomplete Endpoint Tests"
Cohesion: 0.60
Nodes (5): make_app(), FastAPI, test_autocomplete_endpoint_maps_provider_failure_to_502(), test_autocomplete_endpoint_preserves_fl_dynamic_name(), test_autocomplete_endpoint_returns_live_options()

### Community 114 - "Attribute Filter Model + Text Normalizer"
Cohesion: 0.40
Nodes (3): attribute_filter executor op, Normalize Hebrew/mixed text before substring or fuzzy comparison.  Fixes the cla, TextNormalizer

### Community 115 - "Query Request ID Tests"
Cohesion: 0.60
Nodes (4): Request, request_with_id(), test_query_replaces_unsafe_client_request_id(), test_query_reuses_valid_client_request_id()

### Community 117 - "Service: Cubes Autocomplete Request"
Cohesion: 0.50
Nodes (3): CubesAutocompleteRequest, BaseModel, Cubes autocomplete request.

### Community 118 - "Service: MQS Sync Response"
Cohesion: 0.50
Nodes (3): MqsSyncResponse, BaseModel, MQS catalog sync response.

### Community 119 - "Service: Update Layer Request"
Cohesion: 0.50
Nodes (3): BaseModel, Catalog layer metadata update request., UpdateLayerRequest

### Community 120 - "Service: Settings Catalog Status"
Cohesion: 0.50
Nodes (3): CatalogStatus, BaseModel, Catalog connectivity status returned with settings.

### Community 121 - "Service: Settings Update"
Cohesion: 0.50
Nodes (3): BaseModel, Mutable runtime settings request., SettingsUpdate

### Community 122 - "Scripts: Enrich Layer Tags"
Cohesion: 0.67
Nodes (3): clean(), main(), One-off catalog enrichment: generate bilingual alias tags per layer.  Selection

### Community 125 - "backend/README.md: Settings"
Cohesion: 0.67
Nodes (3): Settings model (two-layer store), Settings precedence (env vs runtime overrides), Configuration model (env defaults vs UI overrides)

## Ambiguous Edges - Review These
- `LLMClient protocol` → `agent/router.py`  [AMBIGUOUS]
  backend/app/service/CLAUDE.md · relation: references
- `app/common/CLAUDE.md` → `Python 3.8.10 runtime pin`  [AMBIGUOUS]
  backend/runtime.txt · relation: conceptually_related_to

## Knowledge Gaps
- **199 isolated node(s):** `ailocator-backend`, `eslintConfig`, `nextConfig`, `name`, `version` (+194 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **53 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `LLMClient protocol` and `agent/router.py`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **What is the exact relationship between `app/common/CLAUDE.md` and `Python 3.8.10 runtime pin`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `LayerMeta` connect `Layers Repository (Postgres catalog CRUD)` to `MQS Provider Tests`, `Cubes Gateway & Query Builder + Layer Parameter Models`, `Executor Integration Tests`, `FLAPI Client Factory + Cubes Provider Tests`, `DAL Providers (mixed)`, `Agent Build-Plan Support`, `Backend Tests (mixed)`, `Backend Tests (mixed)`, `Catalog Service (layer CRUD orchestration)`, `FLAPI Provider Package`, `DAL (mixed)`, `Backend Tests (mixed)`, `Tyche Provider Tests`, `Agent Layer Metadata Generation`, `FLAPI Package Provider`, `Backend Service (mixed)`, `Between Executor Op`, `DAL (mixed)`, `FLAPI Packages Provider Tests`, `FLAPI Cube (mixed)`, `Provider Protocol (DIP seam)`, `Backend Service (mixed)`, `Tyche Provider (core)`, `Backend Scripts: Eval`, `Backend Service (mixed)`, `Service: Catalog Router`, `BL Catalog: MQS Sync`?**
  _High betweenness centrality (0.197) - this node is a cross-community bridge._
- **Why does `ProviderError` connect `Provider Error + Tyche Source` to `MQS Provider Tests`, `Cubes Gateway & Query Builder + Layer Parameter Models`, `Spatial Relation Ops (contains/crosses/touches) + Logging`, `FLAPI Client Factory + Cubes Provider Tests`, `DAL Providers (mixed)`, `Layers Repository (Postgres catalog CRUD)`, `Backend Tests (mixed)`, `Catalog Service (layer CRUD orchestration)`, `MQS Entity Mapper`, `DAL (mixed)`, `FLAPI Provider Package`, `Backend Tests (mixed)`, `Tyche Provider Tests`, `Backend Tests (mixed)`, `Agent Layer Metadata Generation`, `MQS Entity Stream`, `Between Executor Op`, `DAL (mixed)`, `DAL (mixed)`, `FLAPI Package Serializer`, `FLAPI Packages Provider Tests`, `MQS Sync Tests`, `Application State Wiring (composition root)`, `FLAPI Cube (mixed)`, `Tyche Gateway`, `Provider Protocol (DIP seam)`, `Tyche Query Builder`, `Backend Service (mixed)`, `Service: Catalog Router`, `FLAPI Cube Parameter Loader`, `Agent: Metadata Sample Builder`?**
  _High betweenness centrality (0.156) - this node is a cross-community bridge._
- **Why does `CatalogService` connect `Catalog Service (layer CRUD orchestration)` to `Backend Tests (mixed)`, `Layer Selection Pipeline (select_layers agent call)`, `Executor Engine (Plan Executor dispatch)`, `Agent BL (mixed)`, `Executor Op Base: Execution Context`, `DAL Providers (mixed)`, `Agent Build-Plan Support`, `Layers Repository (Postgres catalog CRUD)`, `Backend Tests (mixed)`, `Backend Scripts: Eval`, `Provider Error + Tyche Source`, `Backend Tests (mixed)`, `DAL (mixed)`, `Application State Wiring (composition root)`?**
  _High betweenness centrality (0.150) - this node is a cross-community bridge._
- **Are the 46 inferred relationships involving `LayerMeta` (e.g. with `PlanBuilder` and `LayerMetadataGenerator`) actually correct?**
  _`LayerMeta` has 46 INFERRED edges - model-reasoned connections that need verification._
- **Are the 105 inferred relationships involving `ProviderError` (e.g. with `LayerMetadataGenerator` and `._sample()`) actually correct?**
  _`ProviderError` has 105 INFERRED edges - model-reasoned connections that need verification._