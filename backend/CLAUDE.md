# backend/CLAUDE.md

Guidance for working in the LocatoAI backend. Read the root
[`../CLAUDE.md`](../CLAUDE.md) first for the full product context, business rules
(MQS/Cubes bounded loading, agent loop constraints, settings precedence), and gotchas
that apply repo-wide. This file is the backend-specific entry point.

## Where to actually find things

The four backend tiers each have their own `CLAUDE.md` with classes, key methods, and
"where does X live" navigation. **Start at the index:**

**→ [`app/index.md`](app/index.md)** — table of all four tier docs with what each
covers, plus typical navigation paths (adding an endpoint, adding a plan op, fixing a
provider, adding a setting, debugging an error's HTTP status).

| Tier | Doc | One-line summary |
|---|---|---|
| `app/common/` | [`app/common/CLAUDE.md`](app/common/CLAUDE.md) | Dependency-free foundation: env vs. live settings precedence, error hierarchy, CRS/meters math, logging, text normalization. |
| `app/dal/` | [`app/dal/CLAUDE.md`](app/dal/CLAUDE.md) | Implements `bl/ports/`: MQS/Cubes/Tyche provider adapters, provider registry, LLM client, Postgres repositories. |
| `app/bl/` | [`app/bl/CLAUDE.md`](app/bl/CLAUDE.md) | The business core: ports (DIP seam), the 16-step `GeoQueryPlan` + validators, the executor engine + ops, the 3-call agent pipeline, the query orchestrator, the catalog service. |
| `app/service/` | [`app/service/CLAUDE.md`](app/service/CLAUDE.md) | Every HTTP endpoint, DTOs, the composition root (`main.py`), error→HTTP mapping, the `{query, boundaries}` contract, settings secret masking. |

For architecture-level narrative (request lifecycle stage-by-stage, provider deep
dives, the full settings model, running/testing instructions), [`README.md`](README.md)
remains the canonical long-form doc — keep it updated when structure changes. The four
tier `CLAUDE.md` files are the fast reference for "which class/method do I touch,"
`README.md` is the "how does this all fit together" narrative.

## Fast orientation

```
service → bl ← dal
            ↑
         common
```

- `service → bl`: routers call into `bl` objects (orchestrator, catalog, layer
  selector) — never contain business logic themselves (two documented exceptions, see
  `app/service/CLAUDE.md`).
- `dal ← bl`: `bl` depends only on `Protocol`s in `bl/ports/`; `dal` implements them;
  `bl` never imports `dal`.
- `common`: leaf tier, imported by all three others, imports none of them.
- `app/main.py` / `app/application_state_wiring.py`: the composition root — the only
  file that knows and wires every tier together.

## Commands

See the root [`../CLAUDE.md`](../CLAUDE.md) "Commands" section for the full
Docker build/run/test invocations (Python is pinned to exactly 3.8.10; the amd64 Docker
image is the runtime — there is no local ARM-compatible interpreter for this stack).
