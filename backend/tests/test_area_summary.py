from datetime import datetime, timezone
from unittest.mock import Mock

import geopandas as gpd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from shapely.geometry import MultiPolygon, Point, Polygon, mapping

from app.bl.area_summary.area_summary_service import AreaSummaryService
from app.bl.area_summary.models.result import AreaSummaryResult
from app.bl.catalog.catalog_service import CatalogService
from app.bl.catalog.models.layer_field import LayerField
from app.bl.catalog.models.layer_meta import LayerMeta
from app.bl.catalog.models.layer_schema import LayerSchema
from app.dal.providers.registry import InMemoryProviderRegistry
from app.service.area_summary.router import router
from tests.conftest import FakeLayersRepository

NOW = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)
BOUNDARY = Polygon([
    (34.79, 32.07), (34.81, 32.07),
    (34.81, 32.09), (34.79, 32.09),
])


class AreaSummaryProvider:
    def __init__(self, frames):
        self._frames = frames

    def describe_schema(self, layer):
        frame = self._frames.get(layer.id)
        names = [] if frame is None else [
            name for name in frame.columns if name != frame.geometry.name
        ]
        if layer.id == "empty":
            names = ["id", "person_id", "person_name", "observed_at"]
        return LayerSchema(
            layer_id=layer.id, geometry_type="Point",
            fields=[LayerField(name=name, type="string") for name in names],
            temporal_field=(
                "observed_at" if "observed_at" in names else None
            ),
        )

    def fetch_features(self, layer, now=None, geometry=None, limit=None):
        if layer.id == "broken":
            raise RuntimeError("provider is unavailable")
        return self._frames[layer.id].copy()

    def sample_field_values(self, layer, field, limit=20):
        return []


def _layer(layer_id, name, kind, **values):
    tags = values.pop("tags", ["summary:" + kind])
    return LayerMeta(
        id=layer_id, name=name, provider="summary",
        source_url="memory://" + layer_id,
        profiles=["area-summary"], tags=tags,
        **values,
    )


def _frame(values, points):
    return gpd.GeoDataFrame(
        values, geometry=[Point(*point) for point in points], crs="EPSG:4326"
    )


def _service():
    layers = [
        _layer(
            "buildings", "מבנים", "count",
            tags=["summary:count", "summary:group_field:type"],
        ),
        _layer(
            "presence", "חברים", "presence",
            entity_field="person_id", display_field="person_name",
        ),
        _layer(
            "recommendations", "המלצות", "recommendation",
            display_field="label",
            tags=["summary:recommendation", "summary:owner_field:owner"],
        ),
        _layer(
            "encounters", "מפגשים", "encounter",
            entity_field="person_id", display_field="person_name",
        ),
        _layer(
            "empty", "נוכחות ריקה", "presence",
            entity_field="person_id", display_field="person_name",
        ),
        _layer("broken", "שכבה שבורה", "count"),
        LayerMeta(
            id="ignored", name="לא מסכמים", provider="summary",
            source_url="memory://ignored", tags=["summary:count"],
        ),
    ]
    frames = _frames()
    registry = InMemoryProviderRegistry()
    registry.register("summary", AreaSummaryProvider(frames))
    catalog = CatalogService(FakeLayersRepository(layers), registry)
    return AreaSummaryService(catalog, registry)


def _frames():
    return {
        "buildings": _frame(
            {"id": ["b1", "b2", "b3"], "type": ["בניין"] * 3},
            [(34.8000, 32.0800), (34.8002, 32.0800), (35.0, 32.0)],
        ),
        "presence": _frame(
            {
                "id": ["p1", "p2", "p3"],
                "person_id": ["oded", "old", "moshe"],
                "person_name": ["עודד", "ישן", "משה"],
                "observed_at": [
                    "2026-07-24T11:00:00+00:00",
                    "2026-07-22T11:00:00+00:00",
                    "2026-07-24T10:00:00+00:00",
                ],
            },
            [(34.8000, 32.0800)] * 3,
        ),
        "recommendations": _frame(
            {
                "id": ["r1"], "label": ["דקירה של Google Maps"],
                "owner": ["עודד"],
                "observed_at": ["2026-07-24T09:00:00+00:00"],
            },
            [(34.8000, 32.0800)],
        ),
        "encounters": _frame(
            {
                "id": ["e1", "e2", "e3"],
                "person_id": ["oded", "moshe", "dana"],
                "person_name": ["עודד", "משה", "דנה"],
                "observed_at": [
                    "2026-07-24T08:00:00+00:00",
                    "2026-07-24T08:05:00+00:00",
                    "2026-07-24T08:04:00+00:00",
                ],
            },
            [
                (34.8000, 32.0800),
                (34.8001, 32.0800),
                (34.8050, 32.0850),
            ],
        ),
        "broken": _frame({"id": ["x"]}, [(34.8000, 32.0800)]),
        "empty": gpd.GeoDataFrame(
            {"geometry": []}, geometry="geometry", crs="EPSG:4326"
        ),
        "ignored": _frame({"id": ["i"]}, [(34.8000, 32.0800)]),
    }


def test_area_summary_returns_four_fact_types_with_evidence_and_time():
    result = _service().summarize(BOUNDARY, now=NOW)

    assert result.queried_layer_count == 6
    assert result.successful_layer_count == 5
    assert {fact.kind for fact in result.facts} == {
        "count", "presence", "recommendation", "encounter",
    }
    count_fact = next(fact for fact in result.facts if fact.kind == "count")
    assert count_fact.count == 2
    assert {item.feature_id for item in count_fact.evidence} == {"b1", "b2"}
    presence = [
        fact for fact in result.facts
        if fact.kind == "presence" and fact.entities == ["עודד"]
    ][0]
    assert presence.observed_at == datetime(
        2026, 7, 24, 11, 0, tzinfo=timezone.utc
    )
    assert presence.evidence[0].feature_id == "p1"
    assert all("ישן" not in fact.entities for fact in result.facts)
    encounter = next(
        fact for fact in result.facts if fact.kind == "encounter"
    )
    assert set(encounter.entities) == {"עודד", "משה"}
    assert len(encounter.evidence) == 2


def test_area_summary_keeps_partial_results_when_one_layer_fails():
    result = _service().summarize(BOUNDARY, now=NOW)

    assert len(result.facts) == 5
    assert len(result.failures) == 1
    assert result.failures[0].layer_id == "broken"
    assert result.failures[0].error_type == "RuntimeError"
    assert "unavailable" in result.failures[0].message


def test_area_summary_rejects_inverted_window():
    with pytest.raises(ValueError, match="window_start"):
        _service().summarize(
            BOUNDARY,
            window_start=datetime(2026, 7, 25, tzinfo=timezone.utc),
            window_end=NOW,
        )


def test_area_summary_endpoint_exposes_window_and_coverage_contract():
    app = FastAPI()
    app.include_router(router)
    app.state.area_summary = Mock()
    app.state.area_summary.summarize.return_value = AreaSummaryResult(
        generated_at=NOW, window_start=NOW, window_end=NOW,
        queried_layer_count=2, successful_layer_count=1,
    )
    app.state.request_log = Mock()

    response = TestClient(app).post("/api/area-summary", json={
        "boundaries": mapping(MultiPolygon([BOUNDARY])),
        "from": "2026-07-24T08:00:00+00:00",
        "to": "2026-07-24T12:00:00+00:00",
    })

    assert response.status_code == 200
    assert response.json()["queried_layer_count"] == 2
    assert response.json()["successful_layer_count"] == 1
    call = app.state.area_summary.summarize.call_args
    assert call.kwargs["window_start"] == datetime(
        2026, 7, 24, 8, 0, tzinfo=timezone.utc
    )


def test_area_summary_endpoint_requires_timezone_aware_times():
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).post("/api/area-summary", json={
        "boundaries": mapping(MultiPolygon([BOUNDARY])),
        "from": "2026-07-24T08:00:00",
    })

    assert response.status_code == 422
