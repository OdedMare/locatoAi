# Backend Tier Documentation Index

Each backend tier under `app/` has its own `CLAUDE.md` with classes, key methods, and
navigation pointers into the code. Start here, then jump to the tier you need.

Dependency direction: **`service` → `bl` ← `dal`**, both resting on **`common`**.
`bl` owns the interfaces (`bl/ports/`); `dal` implements them; only `app/main.py` /
`app/application_state_wiring.py` (the composition root) knows every tier at once.

| Tier | CLAUDE.md | Covers |
|---|---|---|
| `common/` | [`common/CLAUDE.md`](common/CLAUDE.md) | Env config vs. live runtime settings and their precedence, the 5-type error hierarchy and its HTTP mapping, CRS/meters-math helpers (`geo.py`), console-first dual-destination logging, Hebrew-aware text normalization. Dependency-free foundation — nothing here imports `bl`/`dal`/`service`. |
| `dal/` | [`dal/CLAUDE.md`](dal/CLAUDE.md) | Implementations of the `bl/ports/` interfaces: the MQS, Cubes, and Tyche GIS provider adapters (one-class-per-file collaborators: gateway/query-builder/schema-mapper/etc.), the provider registry, the OpenAI-compatible LLM client with its degradation ladder, the Postgres-backed layers/feedback repositories. |
| `bl/` | [`bl/CLAUDE.md`](bl/CLAUDE.md) | The business logic core: `ports/` (the DIP seam), the 16-step `GeoQueryPlan` contract + validators, the self-registering op executor engine, the three-LLM-call agent pipeline (select layers / build plan / generate layer metadata), the query orchestrator (select→plan→execute→diagnose), and the catalog service (schema cache, MQS sync, Tyche activation). Largest and most important tier. |
| `service/` | [`service/CLAUDE.md`](service/CLAUDE.md) | Every HTTP endpoint (full table), request/response DTOs per router, the composition root (`main.py` / `application_state_wiring.py`) and its `app.state` wiring, the domain-error → HTTP-status mapping, the exact `{query, boundaries}` wire contract, settings secret-masking rules, and the two routers that carry more logic than the "zero-logic router" convention implies. |

## Typical navigation paths

- **Adding an HTTP endpoint or DTO** → `service/CLAUDE.md`.
- **Adding a new plan operation** (e.g. a new spatial relation) → `bl/CLAUDE.md`
  section 3 (`bl/executor/`), then section 2 (`bl/plan/`) for the step model.
- **Changing agent/LLM prompt behavior** → `bl/CLAUDE.md` section 4 (`bl/agent/`);
  prompts are files under `bl/agent/prompts/`, not code.
- **Adding/fixing a GIS provider (MQS/Cubes/Tyche) behavior** → `dal/CLAUDE.md`; the
  interface it must satisfy is documented in `bl/CLAUDE.md` section 1 (`bl/ports/`).
- **Adding a new user-configurable setting** → `common/CLAUDE.md` (env default +
  runtime store), then check `service/CLAUDE.md`'s settings-secrets section if it's
  sensitive.
- **Debugging an error's HTTP status** → `common/CLAUDE.md`'s error hierarchy table,
  cross-referenced with `service/CLAUDE.md`'s error-mapping table (same table, shown
  from each tier's point of view).
