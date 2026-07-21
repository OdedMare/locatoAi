# Agent prompts

The prompt files are the model-facing policy layer for LocatoAI's query pipeline and catalog-metadata assistant. They are loaded by the business layer at runtime, populated with sanitized context, and sent through the OpenAI-compatible LLM port. Keeping prompts outside Python makes model tuning reviewable without mixing wording changes with orchestration code.

`select_layers_diet.md` and `build_plan_diet.md` are the compact production profile.
`llm_diet_mode` selects them at runtime without restarting the backend. Diet prompts must
preserve the same output contracts, operation set, safety rules, sampling tool, and
clarification behavior as their full counterparts. Update and test both profiles whenever
an operation or invariant changes.

The primary mission overlay locates OurForce entities from Tyche and uses matching MQS or
Cubes layers as nearby spatial context. It is a priority path, not a global provider rule:
queries unrelated to OurForce keep the generic subject/reference behavior. Both prompt
stages receive each catalog layer's provider so this choice is based on metadata rather
than names or hardcoded layer IDs.

## Pipeline position

```text
user query
  └─ select_layers.md + sanitized PostgreSQL catalog
       ├─ known layer IDs + Hebrew reasoning
       └─ or short Hebrew clarification
            └─ build_plan.md + selected provider schemas + current time
                 ├─ optional sample_field request (maximum three rounds)
                 ├─ typed GeoQueryPlan
                 └─ or short Hebrew clarification
```

## Files

### `select_layers.md`

Used by `LayerSelector` for model call one. `{catalog}` is replaced with a line-oriented list containing catalog ID, provider, truncated name, up to ten tags, and truncated description. Catalog content is untrusted data, never instructions.

Expected JSON fields include:

- `layer_ids`: IDs that must exist in the provided catalog.
- `reasoning`: short Hebrew reasoning displayed in the UI.
- `clarify`: short Hebrew question when no reliable selection can be made.

Python code deduplicates IDs, preserves returned order, and drops hallucinated IDs. If none remain, it uses the model clarification or a fixed Hebrew fallback.

### `build_plan.md`

Used by `PlanBuilder` for model call two. Runtime substitutions are:

- `{now}`: one UTC timestamp shared by planning and execution.
- `{has_boundaries}`: whether `within_geometry` is legal for this request.
- `{layers}`: selected layer metadata and provider-reported schemas, including safe sample values.

The model may return a `sample_field` tool request to inspect additional distinct values for a selected layer field. The builder allows at most three tool rounds. Tool rounds do not consume the separate validation-retry budget.

The final response must be either a plan matching `GeoQueryPlan` or a short Hebrew clarification. Invalid plans receive one correction attempt containing a bounded validation error and the rejected JSON.

After deterministic execution, zero rows may invoke the planner once more with the
previous plan. The revision must pass normal validation and the code-level
constraint-preservation gate before one re-execution.

### `generate_layer_metadata.md`

Used while a user prepares a catalog layer. The backend fetches the source through
its registered provider, randomly selects at most 10 entities, removes geometry,
bounds property names and values, and sends the preview with the schema and layer
name. The model returns a concise Hebrew description and searchable Hebrew/English
tags. These are suggestions only: the frontend fills editable form fields, and no
catalog row is written until the user explicitly submits it.

For MQS, fixed transport/geometry fields are marked `metadata_relevant=false` and
removed from both the schema preview and sampled records. Only normalized
`property_list` business fields may drive descriptions and tags; missing business
fields produce a provider error instead of generic polygon/clearance metadata.

## Rules split between prompts and code

Prompts express model behavior, examples, and response format. Code remains authoritative for security and correctness:

- Pydantic owns the allowed operation shapes and numeric bounds.
- Semantic validators own catalog IDs, complete target-filter triples, earlier-step references, the required boundary operation, final-output ordering, and terminal-count rules.
- The executor owns spatial semantics and CRS conversions.
- Catalog/provider text and samples are sanitized and truncated before prompt insertion.
- Hallucinated layer IDs are removed in code.
- Clarification fallback remains available even when model output is malformed.

Do not rely on prompt wording as the only enforcement for a rule that protects data, execution, or resource usage.

## Tuning workflow

1. Change the smallest relevant prompt.
2. Keep JSON field names synchronized with the parsers under `select_layers/` or `build_plan/`.
3. Run the backend unit tests.
4. Run `scripts/eval_select_layers.py` after selection-prompt changes.
5. Inspect Hebrew and English cases, ambiguity/clarification cases, token usage, and behavior with untrusted catalog text.
6. Turn real downvotes from the PostgreSQL feedback table into regression cases.

When introducing a new plan operation, update the Pydantic model, validator/executor behavior, this prompt, frontend plan trace, tests, and architecture documentation together.

Cubes trajectory recipes use `netId` as entity identity and `eventTime` as observation
time. Apply temporal filtering before `latest_per_entity` or `movement_direction`.
