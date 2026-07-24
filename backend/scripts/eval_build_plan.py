"""Scored live eval for GeoQueryPlan operation selection.

The cases provide real catalog layer names up front so this isolates planning from
layer selection. It uses the configured LLM, provider schemas, and diet/full setting.

Usage (inside the backend container):
    python scripts/eval_build_plan.py
"""

import sys
import time
from datetime import datetime, timezone

from app.bl.agent.build_plan.plan_builder import PlanBuilder
from app.bl.agent.runtime_diet_mode import RuntimeDietMode
from app.bl.catalog.catalog_service import CatalogService
from app.common.config.settings_provider import get_settings
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.catalog.layers_repository import PostgresLayersRepository
from app.dal.llm.openai_client import OpenAIJsonClient
from app.dal.providers.cubes.provider import CubesProvider
from app.dal.providers.mqs.provider import MqsProvider
from app.dal.providers.registry import InMemoryProviderRegistry
from app.dal.providers.tyche.provider import TycheProvider

PRESENT = object()

CASES = [
    {
        "name": "near-distance-he",
        "query": "בתי ספר במרחק 500 מטר מתחנות רכבת",
        "layers": ("בתי ספר", "תחנות רכבת"),
        "subject": "בתי ספר",
        "ops": ("load", "within_geometry", "near"),
        "context": ("תחנות רכבת",),
        "checks": (("near", "distance_m", 500),),
    },
    {
        "name": "nearest-limit-en",
        "query": "Show the 3 schools nearest to any train station",
        "layers": ("בתי ספר", "תחנות רכבת"),
        "subject": "בתי ספר",
        "ops": ("load", "within_geometry", "nearest_n"),
        "context": ("תחנות רכבת",),
        "checks": (("nearest_n", "count", 3),),
    },
    {
        "name": "multi-reference-he",
        "query": "מצא כוחותינו שנמצאים ליד בתי ספר וגם ליד תחנות רכבת",
        "layers": ("כוחותינו", "בתי ספר", "תחנות רכבת"),
        "subject": "כוחותינו",
        "ops": ("load", "within_geometry", "near_all", "latest_per_entity"),
        "context": ("בתי ספר", "תחנות רכבת"),
        "checks": (("near_all", "distance_m", 300),
                   ("near_all", "count", None)),
    },
    {
        "name": "same-layer-cluster-en",
        "query": "Find groups of 3 schools near each other",
        "layers": ("בתי ספר",),
        "subject": "בתי ספר",
        "ops": ("load", "within_geometry", "cluster"),
        "context": (),
        "checks": (("cluster", "min_group_size", 3),
                   ("cluster", "max_distance_m", 300)),
    },
    {
        "name": "static-direction-en",
        "query": "Show the northernmost kindergarten",
        "layers": ("גני ילדים",),
        "subject": "גני ילדים",
        "ops": ("load", "within_geometry", "directional"),
        "context": (),
        "checks": (("directional", "direction", "north"),
                   ("directional", "count", 1)),
    },
    {
        "name": "movement-direction-he",
        "query": "מצא כוחותינו שזזו דרומה בשעה האחרונה",
        "layers": ("כוחותינו",),
        "subject": "כוחותינו",
        "ops": ("load", "within_geometry", "temporal_filter",
                "movement_direction"),
        "context": (),
        "checks": (("movement_direction", "direction", "south"),),
    },
    {
        "name": "terminal-count-he",
        "query": "כמה בתי ספר נמצאים ליד תחנות רכבת?",
        "layers": ("בתי ספר", "תחנות רכבת"),
        "subject": "בתי ספר",
        "ops": ("load", "within_geometry", "near", "count"),
        "context": ("תחנות רכבת",),
        "checks": (("near", "distance_m", 300),),
    },
    {
        "name": "named-reference-he",
        "query": "בתי ספר ליד כיכר רבין",
        "layers": ("בתי ספר", "כיכרות"),
        "subject": "בתי ספר",
        "ops": ("load", "within_geometry", "near"),
        "context": ("כיכרות",),
        "checks": (("near", "target_field", PRESENT),
                   ("near", "target_operator", PRESENT),
                   ("near", "target_value", PRESENT)),
    },
    {
        "name": "required-boundary-he",
        "query": "הצג בתי ספר באזור המסומן",
        "layers": ("בתי ספר",),
        "subject": "בתי ספר",
        "ops": ("load", "within_geometry"),
        "context": (),
        "checks": (),
    },
    {
        "name": "typo-filter-he",
        "query": "תמצא את בית ספר גרס",
        "layers": ("בתי ספר",),
        "subject": "בתי ספר",
        "ops": ("load", "within_geometry", "attribute_filter"),
        "context": (),
        "checks": (("attribute_filter", "operator", "fuzzy_contains"),),
    },
    {
        "name": "nearest-without-reference-en",
        "query": "Show me the nearest schools",
        "layers": ("בתי ספר",),
        "clarify": True,
    },
    {
        "name": "named-between-he",
        "query": "מצא כוחותינו על הציר בין תל אביב להרצליה",
        "layers": ("כוחותינו", "יישובים"),
        "subject": "כוחותינו",
        "ops": ("load", "within_geometry", "between", "latest_per_entity"),
        "context": ("יישובים",),
        "checks": (("between", "first_target_field", PRESENT),
                   ("between", "second_target_field", PRESENT),
                   ("between", "corridor_width_m", 100)),
    },
    {
        "name": "trajectory-together-en",
        "query": (
            "Find our forces that moved together in the last hour, within "
            "100 meters and a 5 minute time buffer"
        ),
        "layers": ("כוחותינו",),
        "subject": "כוחותינו",
        "ops": ("load", "within_geometry", "temporal_filter",
                "trajectory_relation"),
        "context": (),
        "checks": (("trajectory_relation", "relation", "together"),
                   ("trajectory_relation", "max_distance_m", 100),
                   ("trajectory_relation", "time_tolerance_minutes", 5),
                   ("trajectory_relation", "entity_field", PRESENT),
                   ("trajectory_relation", "time_field", PRESENT)),
    },
    {
        "name": "trajectory-same-destination-en",
        "query": (
            "Find our forces that drove to the same destination in the last "
            "hour, arriving within 10 minutes and 150 meters"
        ),
        "layers": ("כוחותינו",),
        "subject": "כוחותינו",
        "ops": ("load", "within_geometry", "temporal_filter",
                "trajectory_relation"),
        "context": (),
        "checks": (("trajectory_relation", "relation", "same_destination"),
                   ("trajectory_relation", "max_distance_m", 150),
                   ("trajectory_relation", "time_tolerance_minutes", 10)),
    },
    {
        "name": "trajectory-same-time-en",
        "query": (
            "Find our forces that moved at the same time in the last hour "
            "with a 7 minute time buffer; their locations may differ"
        ),
        "layers": ("כוחותינו",),
        "subject": "כוחותינו",
        "ops": ("load", "within_geometry", "temporal_filter",
                "trajectory_relation"),
        "context": (),
        "checks": (("trajectory_relation", "relation", "same_time"),
                   ("trajectory_relation", "time_tolerance_minutes", 7)),
    },
    {
        "name": "trajectory-same-place-different-times-en",
        "query": (
            "Find our forces that passed within 100 meters of the same place "
            "at least 30 minutes apart during the last hour"
        ),
        "layers": ("כוחותינו",),
        "subject": "כוחותינו",
        "ops": ("load", "within_geometry", "temporal_filter",
                "trajectory_relation"),
        "context": (),
        "checks": (("trajectory_relation", "relation",
                    "same_place_different_times"),
                   ("trajectory_relation", "max_distance_m", 100),
                   ("trajectory_relation", "min_time_separation_minutes", 30)),
    },
    {
        "name": "origin-round-trip-en",
        "query": (
            "Find our forces that left at 2026-07-24T16:00:00Z, traveled at "
            "least 500 meters, and returned by 2026-07-24T17:00:00Z within "
            "100 meters of their starting point"
        ),
        "layers": ("כוחותינו",),
        "subject": "כוחותינו",
        "ops": ("load", "within_geometry", "temporal_filter",
                "origin_movement"),
        "context": (),
        "checks": (("origin_movement", "pattern", "round_trip"),
                   ("origin_movement", "entity_field", PRESENT),
                   ("origin_movement", "time_field", PRESENT),
                   ("origin_movement", "min_departure_distance_m", 500),
                   ("origin_movement", "max_return_distance_m", 100)),
    },
    {
        "name": "origin-night-departure-en",
        "query": (
            "Using each first track point as an inferred origin, find our "
            "forces that left it by at least 500 meters during the UTC night "
            "from 2026-07-24T20:00:00Z to 2026-07-25T05:00:00Z"
        ),
        "layers": ("כוחותינו",),
        "subject": "כוחותינו",
        "ops": ("load", "within_geometry", "temporal_filter",
                "origin_movement"),
        "context": (),
        "checks": (("origin_movement", "pattern", "departed"),
                   ("origin_movement", "min_departure_distance_m", 500)),
    },
]


def check_plan(result, case, layers):
    if case.get("clarify"):
        if result.clarify and result.plan is None:
            return True, "CLARIFY: " + result.clarify
        return False, "expected clarify, got a plan"
    if result.plan is None:
        return False, "expected plan, got clarify: " + str(result.clarify)
    errors = _check_ops(result.plan, case)
    errors.extend(_check_roles(result.plan, case, layers))
    errors.extend(_check_fields(result.plan, case.get("checks", ())))
    ops = "/".join(step.op for step in result.plan.steps)
    return not errors, "ops=" + ops + ((" | " + "; ".join(errors)) if errors else "")


def _check_ops(plan, case):
    actual = tuple(step.op for step in plan.steps)
    expected = tuple(case["ops"])
    return [] if actual == expected else [
        "expected ops {}, got {}".format("/".join(expected), "/".join(actual))
    ]


def _check_roles(plan, case, layers):
    by_name = {layer.name: layer.id for layer in layers}
    by_id = {layer.id: layer.name for layer in layers}
    loads = [step.layer for step in plan.steps if step.op == "load"]
    errors = []
    if loads != [by_name[case["subject"]]]:
        errors.append("wrong subject load: " + ",".join(loads))
    expected = {by_name[name] for name in case.get("context", ())}
    if set(plan.context_layers) != expected:
        errors.append("wrong context: " + ",".join(_names(plan.context_layers, by_id)))
    if _reference_ids(plan) != expected:
        errors.append("wrong operation references: " + ",".join(
            _names(_reference_ids(plan), by_id)
        ))
    return errors


def _reference_ids(plan):
    ids = set()
    for step in plan.steps:
        target = getattr(step, "target_layer", None)
        if target:
            ids.add(target)
        ids.update(target.layer for target in getattr(step, "targets", []))
        for field in ("first_target_layer", "second_target_layer"):
            target = getattr(step, field, None)
            if target:
                ids.add(target)
    return ids


def _check_fields(plan, checks):
    errors = []
    for op, field, expected in checks:
        step = next((item for item in plan.steps if item.op == op), None)
        actual = getattr(step, field, None) if step is not None else None
        if expected is PRESENT and actual is None:
            errors.append("{}.{} must be present".format(op, field))
        elif expected is not PRESENT and actual != expected:
            errors.append("{}.{} expected {!r}, got {!r}".format(
                op, field, expected, actual
            ))
    return errors


def _names(ids, by_id):
    return sorted(by_id.get(layer_id, layer_id) for layer_id in ids)


def _resolve_layers(available, names):
    resolved = []
    for name in names:
        matches = [layer for layer in available if layer.name == name]
        if len(matches) != 1:
            raise RuntimeError("expected one catalog layer named {!r}, found {}".format(
                name, len(matches)
            ))
        resolved.append(matches[0])
    return resolved


def _catalog(store, settings):
    providers = InMemoryProviderRegistry()
    providers.register("mqs", MqsProvider(
        store, detail_concurrency=settings.mqs_detail_concurrency
    ))
    providers.register("cubes", CubesProvider(store))
    providers.register("tyche", TycheProvider(store))
    return CatalogService(
        PostgresLayersRepository(store), providers,
        schema_ttl_seconds=settings.schema_cache_ttl_seconds,
    )


def main():
    settings = get_settings()
    store = RuntimeSettingsStore(settings)
    if not store.get().openai_api_key and not store.get().llm_base_url:
        print("No API key and no base_url configured (settings panel). Aborting.")
        return 1
    catalog = _catalog(store, settings)
    available = catalog.list_queryable_layers()
    builder = PlanBuilder(
        OpenAIJsonClient(store), catalog, diet_mode=RuntimeDietMode(store)
    )
    now = datetime.now(timezone.utc)
    print("model:", store.get().llm_model, "| diet:", store.get().llm_diet_mode,
          "| cases:", len(CASES), "\n")
    passed = sum(_run_case(builder, case, available, now) for case in CASES)
    print("\nscore: {}/{}".format(passed, len(CASES)))
    return 0 if passed == len(CASES) else 1


def _run_case(builder, case, available, now):
    started = time.perf_counter()
    try:
        layers = _resolve_layers(available, case["layers"])
        result = builder.build(case["query"], layers, True, now)
        ok, detail = check_plan(result, case, layers)
        usage = result.token_usage or {}
        suffix = "attempts={} tokens={}".format(
            result.attempts, usage.get("total_tokens", "?")
        )
    except Exception as exc:
        ok, detail, suffix = False, "ERROR: {}".format(exc), ""
    ms = int((time.perf_counter() - started) * 1000)
    print("{} {:<28} → {} | {} ({}ms)".format(
        "✓" if ok else "✗", case["name"], detail, suffix, ms
    ))
    return 1 if ok else 0


if __name__ == "__main__":
    sys.exit(main())
