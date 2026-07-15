"""One-off catalog enrichment: generate bilingual alias tags per layer.

Selection quality is capped by the catalog's metadata. This script asks
the configured LLM for search aliases (Hebrew synonyms/colloquial terms +
English equivalents) per layer, merges them into `tags`, and updates
public.layers.

Prints a BACKUP line (JSON of the previous tags) BEFORE applying —
capture stdout to keep it. Restore = UPDATE back from that JSON.

Usage:
    docker exec ailocator-backend python scripts/enrich_layer_tags.py            # dry run (print only)
    docker exec ailocator-backend python scripts/enrich_layer_tags.py --apply    # write to DB
"""

import json
import re
import sys

import psycopg

from app.common.config import get_settings
from app.common.runtime_settings.runtime_settings_store import RuntimeSettingsStore
from app.dal.layers_repository import PostgresLayersRepository
from app.dal.llm.openai_client import OpenAIJsonClient
from app.dal.providers.mqs import MqsProvider

_SYSTEM = """You generate search alias tags for a GIS layer catalog.

Given one layer (Hebrew name, description, current tags, and searchable
property_list fields with bounded sample values), return up to 8
NEW alias tags that help match user queries to this layer:
- Hebrew synonyms, singular form, and common everyday words
- English equivalents (lowercase)
- No duplicates of the current tags, no sentences, each alias <= 24 chars.

Respond ONLY with JSON: {"tags": ["...", "..."]}"""

_MAX_TAGS = 15
_MAX_TAG_CHARS = 24

# Hebrew or Latin letters, digits, spaces, hyphens, Hebrew quote marks.
_VALID_TAG = re.compile(r"^[A-Za-z0-9֐-׿\s\-'\"׳״]+$")


def clean(tags):
    out = []
    for tag in tags:
        if not isinstance(tag, str):
            continue
        tag = " ".join(tag.split())[:_MAX_TAG_CHARS].strip()
        if tag and _VALID_TAG.match(tag) and tag not in out:
            out.append(tag)
    return out


def main() -> int:
    apply = "--apply" in sys.argv
    settings = get_settings()
    store = RuntimeSettingsStore(settings)
    repository = PostgresLayersRepository(store)
    llm = OpenAIJsonClient(store)
    mqs = MqsProvider(store)

    layers = repository.list_layers()
    print("BACKUP", json.dumps({l.id: l.tags for l in layers}, ensure_ascii=False))
    print()

    updates = []
    for layer in layers:
        searchable_fields = []
        if layer.provider == "mqs":
            try:
                schema = mqs.describe_schema(layer)
                searchable_fields = [
                    {
                        "name": field.name,
                        "type": field.type,
                        "samples": field.samples[:5],
                    }
                    for field in schema.fields
                ]
            except Exception as exc:
                print("! {:<28} property_list unavailable: {}".format(
                    layer.name, exc
                ))
        user = json.dumps(
            {
                "name": layer.name,
                "description": layer.description,
                "current_tags": layer.tags,
                "searchable_fields": searchable_fields,
            },
            ensure_ascii=False,
        )
        try:
            data = llm.complete_json(system=_SYSTEM, user=user)
        except Exception as exc:
            print("✗ {:<28} ERROR: {}".format(layer.name, exc))
            continue
        new_tags = clean(data.get("tags") or [])
        merged = clean(layer.tags + new_tags)[:_MAX_TAGS]
        added = [t for t in merged if t not in layer.tags]
        updates.append((layer.id, merged))
        print("{} {:<28} + {}".format("✓" if added else "=", layer.name, ", ".join(added)))

    if not apply:
        print("\nDRY RUN — rerun with --apply to write {} updates".format(len(updates)))
        return 0

    with psycopg.connect(store.get().database_url) as conn:
        for layer_id, tags in updates:
            conn.execute(
                "UPDATE {} SET tags = %s, updated_at = now() WHERE id = %s".format(
                    store.get().quoted_layers_table()
                ),
                (tags, layer_id),
            )
    print("\napplied {} updates".format(len(updates)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
