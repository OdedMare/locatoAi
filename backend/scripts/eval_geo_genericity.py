"""Live provider-neutral planning eval with synthetic layer schemas.

Runs without Postgres or GIS providers:
    python scripts/eval_geo_genericity.py
"""

import sys
from datetime import datetime, timezone

from app.bl.agent.build_plan.plan_builder import PlanBuilder
from app.bl.agent.runtime_diet_mode import RuntimeDietMode
from app.bl.catalog.models.layer_field import LayerField
from app.bl.catalog.models.layer_meta import LayerMeta
from app.bl.catalog.models.layer_schema import LayerSchema
from app.common.config.settings_provider import get_settings
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.llm.openai_client import OpenAIJsonClient

FRIENDS = LayerMeta(
    id="synthetic-friends", name="חברים", provider="telemetry-x",
    source_url="synthetic://friends", entity_field="friend_key",
    display_field="nickname", profiles=["friends"],
)
PLACES = LayerMeta(
    id="synthetic-places", name="מקומות מפגש", provider="places-y",
    source_url="synthetic://places", display_field="place_title",
)


class SyntheticCatalog:
    _SCHEMAS = {
        FRIENDS.id: LayerSchema(
            layer_id=FRIENDS.id, geometry_type="Point",
            fields=[
                LayerField(name="friend_key", type="string"),
                LayerField(name="nickname", type="string"),
                LayerField(name="seen_at", type="date"),
            ],
            entity_field="friend_key", temporal_field="seen_at",
            display_field="nickname",
        ),
        PLACES.id: LayerSchema(
            layer_id=PLACES.id, geometry_type="Point",
            fields=[LayerField(name="place_title", type="string")],
            display_field="place_title",
        ),
    }

    def get_schema(self, layer_id):
        return self._SCHEMAS[layer_id]

    def sample_field(self, layer_id, field, limit=20):
        return []


CASES = [
    (
        "הצג את המיקום האחרון של כל חבר",
        [FRIENDS],
        ("load", "latest_per_entity"),
        ("latest_per_entity", "friend_key", "seen_at"),
    ),
    (
        "מצא חברים שזזו צפונה בשעה האחרונה",
        [FRIENDS],
        ("load", "temporal_filter", "movement_direction"),
        ("movement_direction", "friend_key", "seen_at"),
    ),
    (
        "מצא חברים ליד מקומות מפגש",
        [FRIENDS, PLACES],
        ("load", "near"),
        None,
    ),
]


def main() -> int:
    store = RuntimeSettingsStore(get_settings())
    builder = PlanBuilder(
        OpenAIJsonClient(store), SyntheticCatalog(),
        diet_mode=RuntimeDietMode(store),
    )
    passed = 0
    for query, layers, expected_ops, role_check in CASES:
        result = builder.build(
            query, layers, has_boundaries=False,
            now=datetime.now(timezone.utc),
        )
        actual = tuple(step.op for step in result.plan.steps) if result.plan else ()
        ok = actual == expected_ops
        if ok and role_check:
            operation, entity, temporal = role_check
            step = next(item for item in result.plan.steps if item.op == operation)
            ok = step.entity_field == entity and step.time_field == temporal
        passed += int(ok)
        print("{} {} → {}".format("✓" if ok else "✗", query, actual))
    print("score: {}/{}".format(passed, len(CASES)))
    return 0 if passed == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(main())
