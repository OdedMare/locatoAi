# `app/common/` — Cross-Cutting Foundation Tier

Read this when you need env/settings behavior, error types, CRS/geo math, logging, or
text normalization. See [`../index.md`](../index.md) for how this tier fits with
`bl/`, `dal/`, and `service/`.

## What this tier is

Dependency-free foundation code. **Confirmed by grep: no file under `common/` imports
from `app.bl`, `app.dal`, or `app.service`.** The dependency arrow only ever points the
other way (`bl`/`dal`/`service` → `common`). Keep it that way — nothing here should ever
need to know about plans, providers, or routers.

```
app/common/
├── config/
│   ├── settings.py                 env-driven Settings (defaults)
│   └── settings_provider.py        cached Settings() factory
├── utils/
│   ├── geo_utils.py                CRS/reprojection helpers
│   └── normalizer.py               Hebrew-aware text normalization
├── logging/
│   ├── console_logger.py           ConsoleFirstLogger
│   └── configurator.py             structlog + stdlib logging setup
├── errors/                         one exception type per file, mapped to HTTP in main.py
└── runtime_settings/                the live-override settings store
```

## Settings: `config/settings.py` + `config/settings_provider.py` vs. `runtime_settings/`

**Precedence: `runtime-settings.json` (UI-edited) > environment variables (`Settings`
defaults) > dataclass field defaults.**

- **`class Settings(BaseSettings)`** (`config/settings.py`) — every field reads from an env var
  named `AILOCATOR_<FIELD>` (prefix `AILOCATOR_`) or a `.env` file. All fields have
  defaults so the app boots with zero env vars set. Key groups: `database_url` (+
  optional `database_user/password/host/port/name` overrides), `layers_table` /
  `feedback_table`, `llm_model` / `llm_diet_mode` / `llm_base_url`, `openai_api_key`
  (reads the raw `OPENAI_API_KEY` env var, bypassing the `AILOCATOR_` prefix),
  `mqs_base_url` / `mqs_user_id` / `mqs_verify_tls` / `mqs_detail_concurrency`,
  `cubes_base_url` / `cubes_token` / `cubes_verify_tls`, `tyche_base_url` /
  `tyche_username` / `tyche_token` / `tyche_verify_tls`, `runtime_settings_file`,
  `schema_cache_ttl_seconds`, `request_log_path`.
  - `SettingsProvider.get()` (`config/settings_provider.py`, `@lru_cache`) memoizes one
    `Settings()` instance per process. `settings_provider.get_settings = SettingsProvider.get`.
  - **`get_settings()` is called exactly once**, at startup in `main.py`, purely to seed
    the `RuntimeSettingsStore`. Nothing else should call it.

- **`runtime_settings/runtime_settings.py`** — `class RuntimeSettings` (`@dataclass`):
  a mutable mirror of most `Settings` fields (excludes `runtime_settings_file`,
  `schema_cache_ttl_seconds`, `request_log_path` — those stay boot-time-only). Methods
  `quoted_layers_table()` / `quoted_feedback_table()` double-quote each
  dot-separated identifier part for safe SQL interpolation.

- **`runtime_settings/normalizers.py`** — `class RuntimeSettingsNormalizer`: validates
  and cleans values before they enter the store (all raise `ValueError` on bad input).
  `llm_base_url` / `mqs_base_url` / `cubes_base_url` / `tyche_base_url` strip known
  suffixes and require an `http(s)://` scheme. `database_url` strips a leading `jdbc:`
  and requires `postgresql://`/`postgres://`. `layers_table` (also used for
  `feedback_table`) validates against `^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$`
  — **this exists because the value is interpolated into SQL**; never loosen it.

- **`runtime_settings/runtime_settings_store.py`** — `class RuntimeSettingsStore`, the
  single source of truth for **live** configuration:
  - `__init__(self, env: Settings)` — seeds `RuntimeSettings` from `env`, then if
    `runtime-settings.json` exists, overlays it **leniently** (`strict=False`): a bad
    saved value is skipped, not fatal, so a corrupt file can't block boot.
  - `get() -> RuntimeSettings` — same instance every call, mutated in place by `update`.
  - `update(patch: dict) -> RuntimeSettings` — applies **strictly** (`strict=True`, bad
    value raises `ValueError`), then persists the whole dataclass to
    `runtime-settings.json` as pretty JSON. This is what `PUT /api/settings` calls.
  - Nullable-clearable fields (`_NULLABLE`: `database_port`, `llm_base_url`,
    `mqs_base_url`, `mqs_user_id`, `cubes_base_url`, `tyche_base_url`,
    `tyche_username`) treat an incoming `None`/`""` as "clear this field" — e.g. this is
    how a provider gets disabled again. For every other field, `None` means "not
    provided," i.e. keep the current value.
  - Constructed **once** in `application_state_wiring.py`, stored at
    `app.state.settings_store` — a long-lived singleton per process.

**Practical rule for a new dev:** every DAL provider/repository and the LLM client read
`settings_store.get().<field>` on **every call**, never `get_settings()` again after
boot — this is what makes the Settings UI a live-override layer with no restart needed.
To add a new user-configurable setting: add it to `Settings` (env default) *and*
`RuntimeSettings` (dataclass field), wire the seed in `RuntimeSettingsStore.__init__`,
add a normalizer if it needs validation, and read it via `store.get().<field>`.

## Errors: `errors/`

`class AiLocatorError(Exception)` (`ailocator_error.py`) is the base for all domain
errors. Each subclass lives in its own file and is mapped to an HTTP status by
`app/service/errors/registry.py`:

| Class | File | Meaning | HTTP status |
|---|---|---|---|
| `LayerNotFoundError` | `layer_not_found_error.py` | Catalog has no such layer id (`__init__(self, layer_id)`) | 404 |
| `PlanValidationError` | `plan_validation_error.py` | Plan is structurally/semantically invalid | 422 |
| `ProviderError` | `provider_error.py` | A GIS/LLM provider failed to serve schema or features | 502 |
| `ExecutionError` | `execution_error.py` | A plan step failed at execution time | 400 |
| `AgentError` | `agent_error.py` | LLM call failed (missing key, network, unparseable output) | 503 |
| *(anything else)* | — | Unexpected exception | 500 |

Each is caught by `ErrorHandler(status_code)`, which logs via
`request.app.state.request_log` and returns
`{"status": "error", "request_id", "detail", "error_type", "pipeline_trace"}` —
`detail` is genericized to `"Internal server error"` only for the 500 catch-all; every
typed domain error exposes its real message. Raise the typed error from `bl`/`dal` and
let this registry do the HTTP mapping — don't `try/except` + `HTTPException` in routers
for these five types.

## Geo math: `utils/geo_utils.py`

**All meters math goes through here — never do distance/buffer math directly in WGS84
degrees.** `class GeoUtils`:
- `metric_crs_for(*frames) -> CRS` — picks a locally-accurate metric CRS by
  reprojecting to WGS84, taking the combined-bounds center, and calling
  `estimate_utm_crs()` (falls back to Web Mercator `EPSG:3857` if that fails or all
  frames are empty). **Note:** `ISRAEL_TM = "EPSG:2039"` is defined as a constant but
  `metric_crs_for` does not force it — it dynamically estimates a UTM zone from the
  data's own bounds instead.
- `to_metric(gdf, crs=None)` / `to_wgs84(gdf)` — reproject helpers.
- `buffer_wgs84_geometry(geometry, distance_m)` — the safe way to buffer a WGS84
  (lon/lat) geometry by a distance in meters: reprojects to a metric CRS, buffers,
  reprojects back.
- `empty_features_gdf()` — a consistent empty `GeoDataFrame` (`geometry` column,
  `crs=WGS84`) for "no results."

Module-level aliases exist for every method (`from app.common.utils.geo_utils import to_metric`).

## Logging: `logging/console_logger.py` + `logging/configurator.py`

Console-first, dual-destination structured logging:

- **`LoggingConfigurator.configure(request_log_path) -> ConsoleFirstLogger`** — called
  once at startup with `settings.request_log_path` (default `backend/logs/requests.jsonl`).
  Wires two stdlib loggers (`"ailocator.requests"` → file, `"ailocator.requests.console"`
  → console) plus the general `"app"` logger → console, all `propagate=False`.
  Configures `structlog` globally to render every line as ISO-timestamped JSON.
- **`class ConsoleFirstLogger`** — `bind(**context)` returns a new logger with extra
  bound context (e.g. `request_id`); `info`/`warning`/`error`/`exception` write to
  **console first, then the persistent file** — if file writing fails, the console has
  already captured the event. Stored at `app.state.request_log`; this is what
  `ErrorHandler` looks up.

Two destinations: stdout (dev visibility) and `backend/logs/requests.jsonl`
(append-only, durable, configurable via `AILOCATOR_REQUEST_LOG_PATH`).

## Text: `utils/normalizer.py`

`class TextNormalizer` / `normalize_text = TextNormalizer.normalize` — NFKC-normalizes,
strips Hebrew niqqud and punctuation (`״`/`׳` and ASCII stand-ins), folds Hebrew final
letters to regular form (`ך→כ`, `ם→מ`, `ן→נ`, `ף→פ`, `ץ→צ`), collapses whitespace/`-`/
`_`/`.` runs, strips and casefolds. Fixes mismatches like `"תל אביב"` vs `"ת״א"` or
`"בית ספר"` vs `"בית-ספר"`. **Always applied before `attribute_filter`'s
`contains`/`eq` checks** in `bl/executor/ops/attribute_filter.py` — a leaf utility
consumed by `bl`, confirming the dependency direction never reverses.

## Getting oriented

- Need a new setting? Start in `config/settings.py` + `runtime_settings/runtime_settings.py`.
- Need to raise a typed failure? Pick from `errors/` — don't invent a new exception type
  without a good reason; the HTTP mapping lives in `app/service/errors/registry.py`.
- Doing distance/buffer/reprojection? Everything you need is a `GeoUtils` static method.
- Adding a log line? Use the `ConsoleFirstLogger` at `app.state.request_log`, not raw
  `logging.getLogger`.
