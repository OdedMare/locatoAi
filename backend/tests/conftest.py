from datetime import datetime, timezone
from itertools import count
from pathlib import Path
from typing import List, Optional, Tuple

import pytest

from app.bl.catalog.catalog_service import CatalogService
from app.bl.executor.engine.plan_executor import PlanExecutor
from app.bl.ports.layer_meta import LayerMeta
from tests.mock_gis_provider import MockGisProvider
from app.dal.providers.registry import InMemoryProviderRegistry

DATA_DIR = Path(__file__).parent.parent / "data"
FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Tests use readable layer ids; production uses catalog UUIDs — the code
# never assumes id shape.
LAYERS = [
    LayerMeta(
        id="schools", name="בתי ספר", description="כל מוסדות החינוך",
        tags=["education", "school"], provider="arcgis",
        source_url="https://provider.example/schools",
    ),
    LayerMeta(
        id="roundabouts", name="כיכרות", description="כיכרות עירוניות",
        tags=["roads", "roundabout"], provider="arcgis",
        source_url="https://provider.example/roundabouts",
    ),
    LayerMeta(
        id="accidents", name="אירועי תאונות", description="תאונות דרכים",
        tags=["traffic", "accident", "event"], provider="arcgis",
        source_url="https://provider.example/accidents",
    ),
    LayerMeta(
        id="empty-layer", name="שכבה ריקה", description="ללא קובץ נתונים",
        tags=[], provider="arcgis",
        source_url="https://provider.example/nodata",
    ),
]


class FakeLayersRepository:
    """In-memory implementation of the LayersRepository port."""

    def __init__(self, layers: List[LayerMeta]):
        self._layers = {layer.id: layer for layer in layers}

    def list_layers(self) -> List[LayerMeta]:
        return list(self._layers.values())

    def get_layer(self, layer_id: str) -> Optional[LayerMeta]:
        return self._layers.get(layer_id)

    _ids = count(1)

    def add_layer(self, layer: LayerMeta) -> LayerMeta:
        created = layer.model_copy(update={"id": f"gen-{next(self._ids)}"})
        self._layers[created.id] = created
        return created

    def upsert_layer(self, layer: LayerMeta) -> Tuple[LayerMeta, bool]:
        for existing in self._layers.values():
            if (
                existing.provider == layer.provider
                and existing.source_url == layer.source_url
            ):
                updated = existing.model_copy(
                    update={"name": layer.name, "description": layer.description}
                )  # tags preserved, like the Postgres repository
                self._layers[existing.id] = updated
                return updated, False
        return self.add_layer(layer), True


@pytest.fixture
def providers() -> InMemoryProviderRegistry:
    registry = InMemoryProviderRegistry()
    registry.register("arcgis", MockGisProvider(DATA_DIR))
    return registry


@pytest.fixture
def catalog(providers) -> CatalogService:
    return CatalogService(FakeLayersRepository(LAYERS), providers)


@pytest.fixture
def executor(catalog, providers) -> PlanExecutor:
    return PlanExecutor(catalog, providers)


@pytest.fixture
def frozen_now() -> datetime:
    """Accident timestamps are generated relative to now — freeze it."""
    return datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc)
