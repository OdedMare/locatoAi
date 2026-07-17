"""Validated activation of the singleton Tyche Our Forces catalog layer."""

from typing import List, Optional, Tuple
from uuid import uuid4

from app.bl.ports.layer_meta import LayerMeta
from app.bl.ports.layers_repository import LayersRepository
from app.bl.ports.provider import Provider

TYCHE_SOURCE = "tyche://ourforces"

_NAME = "כוחותינו"
_DESCRIPTION = (
    "שכבת Tyche של דיווחי מיקום מתוזמנים לכוחותינו. כוללת מזהה רשת, "
    "סוג כוח, יחידה, סימן קריאה, זמני אירוע והגעה וגאומטריה; מתאימה "
    "להצגת מיקום אחרון, סינון זמן וסוג כוח, קרבה, קיבוץ וניתוח כיוון תנועה."
)
_LEGACY_DESCRIPTIONS = {
    "מיקומים ואירועי זמן של כוחותינו ממערכת Tyche",
}
_TAGS = [
    "כוחותינו", "כוחות", "כלי רכב", "יחידות", "סימן קריאה",
    "מיקום בזמן אמת", "תנועת כוחות", "מסלול תנועה", "כיוון נסיעה",
    "אירועי מיקום", "our forces", "forces", "vehicles", "units",
    "call sign", "live location", "force tracking", "movement",
    "trajectory", "tyche",
]


class TycheLayerActivator:
    def activate(
        self, repository: LayersRepository, provider: Provider,
    ) -> Tuple[LayerMeta, bool, int]:
        existing = self._existing(repository)
        candidate = self._candidate()
        sample = provider.fetch_features(candidate, limit=1)
        activated, created = repository.upsert_layer(candidate)
        persisted = repository.update_layer_metadata(
            activated.id, _NAME, self._description(existing), self._tags(existing)
        )
        return persisted, created, len(sample)

    @staticmethod
    def _candidate() -> LayerMeta:
        return LayerMeta(
            id=str(uuid4()), name=_NAME, description=_DESCRIPTION, tags=_TAGS,
            provider="tyche", source_url=TYCHE_SOURCE,
        )

    @staticmethod
    def _existing(repository: LayersRepository) -> Optional[LayerMeta]:
        return next((
            layer for layer in repository.list_layers()
            if layer.provider == "tyche" and layer.source_url == TYCHE_SOURCE
        ), None)

    @staticmethod
    def _tags(existing: Optional[LayerMeta]) -> List[str]:
        tags = existing.tags if existing is not None else []
        return list(dict.fromkeys([*_TAGS, *tags]))

    @staticmethod
    def _description(existing: Optional[LayerMeta]) -> str:
        if existing is None or not existing.description.strip():
            return _DESCRIPTION
        if existing.description.strip() in _LEGACY_DESCRIPTIONS:
            return _DESCRIPTION
        return existing.description


activate_tyche_layer = TycheLayerActivator().activate
