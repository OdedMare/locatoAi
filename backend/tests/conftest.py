from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import pytest

from app.bl.catalog.catalog_service import CatalogService
from app.bl.executor.engine import PlanExecutor
from app.bl.ports import LayerMeta
from app.dal.providers.arcgis_mock import MockArcgisProvider
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


@pytest.fixture
def providers() -> InMemoryProviderRegistry:
    registry = InMemoryProviderRegistry()
    registry.register("arcgis", MockArcgisProvider(DATA_DIR))
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
