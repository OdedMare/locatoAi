"""Validated activation of the singleton Tyche Our Forces catalog layer."""

from typing import Tuple
from uuid import uuid4

from app.bl.ports.layer_meta import LayerMeta
from app.bl.ports.layers_repository import LayersRepository
from app.bl.ports.provider import Provider

TYCHE_SOURCE = "tyche://ourforces"

_NAME = "כוחותינו"
_DESCRIPTION = "מיקומים ואירועי זמן של כוחותינו ממערכת Tyche"
_TAGS = [
    "כוחותינו", "כוחות", "רכב", "יחידות", "מיקום בזמן אמת",
    "our forces", "vehicles", "units", "live location", "tyche",
]


def activate_tyche_layer(
    repository: LayersRepository, provider: Provider,
) -> Tuple[LayerMeta, bool, int]:
    """Probe one row, then upsert; a failed probe never changes the catalog."""
    candidate = LayerMeta(
        id=str(uuid4()), name=_NAME, description=_DESCRIPTION, tags=_TAGS,
        provider="tyche", source_url=TYCHE_SOURCE,
    )
    sample = provider.fetch_features(candidate, limit=1)
    activated, created = repository.upsert_layer(candidate)
    persisted = repository.get_layer(activated.id) or activated
    return persisted, created, len(sample)
