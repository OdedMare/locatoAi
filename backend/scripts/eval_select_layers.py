"""Scored eval: canned queries (Hebrew + English) through layer selection
against the REAL Postgres catalog and the configured LLM.

Each case states the EXPECTED layer names (or CLARIFY). The run fails
(exit 1) when any case misses — run after every prompt/model change.

Usage (inside the backend container):
    python scripts/eval_select_layers.py

Add every real-world miss as a new case here.
"""

import sys
import time

from app.bl.agent.select_layers.layer_selector import LayerSelector
from app.bl.catalog.catalog_service import CatalogService
from app.common.config.settings_provider import get_settings
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.catalog.layers_repository import PostgresLayersRepository
from app.dal.llm.openai_client import OpenAIJsonClient
from app.dal.providers.cubes.provider import CubesProvider
from app.dal.providers.mqs.provider import MqsProvider
from app.dal.providers.registry import InMemoryProviderRegistry
from app.dal.providers.tyche.provider import TycheProvider

CLARIFY = "CLARIFY"

# (query, required layer names, allowed extra layer names)
# - required: every name must be selected
# - allowed extras: may appear without failing (e.g. יישובים for "in <city>")
# - CLARIFY as required means the model must ask instead of selecting
CASES = [
    ("Find schools near train stations in Tel Aviv",
     {"בתי ספר", "תחנות רכבת"}, {"יישובים", "שכונות"}),
    ("Show accidents from yesterday on Highway 6",
     {"אירועי תאונות"}, {"כבישים"}),
    ("בתי ספר ליד כיכר רבין",
     {"בתי ספר", "כיכרות"}, set()),
    ("הפגנות במרכז העיר",
     {"הפגנות ואירועים"}, {"יישובים", "שכונות"}),
    ("hospitals near parks",
     {"בתי חולים", "פארקים"}, set()),
    ("עמדות טעינה לרכב חשמלי בחניונים",
     {"עמדות טעינה לרכב חשמלי", "חניונים"}, set()),
    ("show me buildings",
     {CLARIFY}, set()),
    ("the northernmost kindergarten in Holon",
     {"גני ילדים"}, {"יישובים", "שכונות"}),
    ("אירועי פשיעה ליד תחנות משטרה",
     {"אירועי פשיעה", "תחנות משטרה"}, set()),
    ("beaches with parking nearby",
     {"חופי רחצה", "חניונים"}, set()),
    ("תמצא את הבית קולנוע הכי צפוני",
     {"בתי קולנוע"}, {"יישובים"}),
    ("תמצא לי מסעדות כשרות",
     {CLARIFY}, set()),
    # --- hard cases: typos, slang, indirect phrasing ---
    ("בתיספר בסביבה",  # typo: missing space
     {"בתי ספר"}, {"יישובים", "שכונות"}),
    ("מקומות לשחות",  # indirect: swimming → beaches
     {"חופי רחצה"}, {"פארקים", "שמורות טבע"}),
    ("kindergartens near the sea",
     {"גני ילדים", "חופי רחצה"}, set()),
    ("where can I charge my tesla",  # brand name → EV charging
     {"עמדות טעינה לרכב חשמלי"}, {"חניונים"}),
    ("איפה אפשר להחנות את האוטו ליד הים?",  # slang, indirect
     {"חניונים", "חופי רחצה"}, set()),
    ("מוסדות אקדמיים",  # formal register
     {"אוניברסיטאות"}, {"בתי ספר"}),
    ("תאונות קשות השבוע",
     {"אירועי תאונות"}, set()),
    ("מגרשי כדורגל",  # nothing fits — must not guess playgrounds
     {CLARIFY}, set()),
    ("תביא לי את כל הכיכרות שליד בית ומטע זיתים",
     {CLARIFY}, set()),
    ("תמצא לי את החייל שזז בשעה האחרונה",
     {"כוחותינו"}, set()),
    ("תמצא לי את הטנק שזז מצפון לדרם",
     {"כוחותינו"}, set()),
    ("תמצא לי את החייל שהיה על הציר בין תל אביב להרצליה",
     {"כוחותינו", "יישובים"}, {"כבישים"}),
    ("תמצא לי טנקים ליד בתי ספר",
     {"כוחותינו", "בתי ספר"}, set()),
    ("find our forces near train stations",
     {"כוחותינו", "תחנות רכבת"}, set()),
]


def check(selection, required, allowed):
    """Return (ok, detail)."""
    if CLARIFY in required:
        if selection.clarify:
            return True, "CLARIFY: " + selection.clarify
        return False, "expected clarify, got: " + ", ".join(
            l.name for l in selection.layers
        )
    got = {layer.name for layer in selection.layers}
    missing = required - got
    unexpected = got - required - allowed
    if missing or unexpected:
        detail = "got: " + (", ".join(sorted(got)) or "(clarify: %s)" % selection.clarify)
        if missing:
            detail += " | MISSING: " + ", ".join(sorted(missing))
        if unexpected:
            detail += " | UNEXPECTED: " + ", ".join(sorted(unexpected))
        return False, detail
    return True, ", ".join(l.name for l in selection.layers)


def main() -> int:
    settings = get_settings()
    store = RuntimeSettingsStore(settings)
    if not store.get().openai_api_key and not store.get().llm_base_url:
        print("No API key and no base_url configured (settings panel). Aborting.")
        return 1

    providers = InMemoryProviderRegistry()
    providers.register("mqs", MqsProvider(store))
    providers.register("cubes", CubesProvider(store))
    providers.register("tyche", TycheProvider(store))
    catalog = CatalogService(PostgresLayersRepository(store), providers)
    selector = LayerSelector(OpenAIJsonClient(store), catalog)

    print("model:", store.get().llm_model, "| layers in catalog:",
          len(catalog.list_layers()), "\n")

    passed = 0
    for query, required, allowed in CASES:
        started = time.perf_counter()
        try:
            selection = selector.select(query)
            ms = int((time.perf_counter() - started) * 1000)
            ok, detail = check(selection, required, allowed)
        except Exception as exc:
            ok, detail, ms = False, "ERROR: %s" % exc, 0
        passed += 1 if ok else 0
        print("{} {:<52} → {} ({}ms)".format("✓" if ok else "✗", query, detail, ms))

    total = len(CASES)
    print("\nscore: {}/{}".format(passed, total))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
