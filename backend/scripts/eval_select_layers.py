"""Eval: run canned queries (Hebrew + English) through layer selection
against the REAL Postgres catalog and the configured LLM.

Usage (inside the backend container or an env with deps + DB access):
    python scripts/eval_select_layers.py

Requires an API key: set it in the UI settings panel, OPENAI_API_KEY,
or runtime-settings.json.
"""

import sys
import time

from app.bl.agent.select_layers import LayerSelector
from app.bl.catalog.catalog_service import CatalogService
from app.common.config import get_settings
from app.common.runtime_settings import RuntimeSettingsStore
from app.dal.layers_repository import PostgresLayersRepository
from app.dal.llm.openai_client import OpenAIJsonClient
from app.dal.providers.arcgis_mock import MockArcgisProvider
from app.dal.providers.registry import ProviderRegistryImpl

QUERIES = [
    "Find schools near train stations in Tel Aviv",
    "Show accidents from yesterday on Highway 6",
    "בתי ספר ליד כיכר רבין",
    "הפגנות במרכז העיר",
    "hospitals near parks",
    "עמדות טעינה לרכב חשמלי בחניונים",
    "show me buildings",  # ambiguous — expect a clarify question
    "the northernmost kindergarten in Holon",
    "אירועי פשיעה ליד תחנות משטרה",
    "beaches with parking nearby",
]


def main() -> int:
    settings = get_settings()
    store = RuntimeSettingsStore(settings)
    if not store.get().openai_api_key and not store.get().llm_base_url:
        print("No API key and no base_url configured (settings panel). Aborting.")
        return 1

    providers = ProviderRegistryImpl()
    providers.register("arcgis", MockArcgisProvider(settings.data_dir))
    catalog = CatalogService(PostgresLayersRepository(store), providers)
    selector = LayerSelector(OpenAIJsonClient(store), catalog)

    print("model:", store.get().llm_model, "| layers in catalog:",
          len(catalog.list_layers()), "\n")

    failures = 0
    for query in QUERIES:
        started = time.perf_counter()
        try:
            selection = selector.select(query)
            ms = int((time.perf_counter() - started) * 1000)
            if selection.clarify:
                print("? {:<55} → CLARIFY: {} ({}ms)".format(query, selection.clarify, ms))
            else:
                names = ", ".join(l.name for l in selection.layers)
                print("✓ {:<55} → {} ({}ms)".format(query, names, ms))
        except Exception as exc:
            failures += 1
            print("✗ {:<55} → ERROR: {}".format(query, exc))

    print("\ndone —", failures, "errors")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
