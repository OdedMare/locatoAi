from datetime import datetime, timezone
from unittest.mock import Mock

import geopandas as gpd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from shapely.geometry import MultiPolygon, Point, Polygon, mapping

from app.bl.catalog.catalog_service import CatalogService
from app.bl.catalog.models.layer_field import LayerField
from app.bl.catalog.models.layer_meta import LayerMeta
from app.bl.catalog.models.layer_schema import LayerSchema
from app.bl.ranking.models.result import RankingResult
from app.bl.ranking.ranking_service import RankingService
from app.dal.providers.registry import InMemoryProviderRegistry
from app.service.ranking.router import router
from tests.conftest import FakeLayersRepository

NOW = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)
BOUNDARY = Polygon([
    (34.79, 32.07), (34.81, 32.07),
    (34.81, 32.09), (34.79, 32.09),
])


class RankingProvider:
    def __init__(self, frames):
        self._frames = frames

    def describe_schema(self, layer):
        frame = self._frames.get(layer.id)
        names = [] if frame is None else [
            name for name in frame.columns if name != frame.geometry.name
        ]
        return LayerSchema(
            layer_id=layer.id, geometry_type="Point",
            fields=[LayerField(name=name, type="string") for name in names],
            display_field="name" if "name" in names else None,
        )

    def fetch_features(self, layer, now=None, geometry=None, limit=None):
        if layer.id == "broken":
            raise RuntimeError("provider is unavailable")
        return self._frames[layer.id].copy()

    def sample_field_values(self, layer, field, limit=20):
        return []


def _layer(layer_id, name, tags, **values):
    return LayerMeta(
        id=layer_id, name=name, provider="ranking",
        source_url="memory://" + layer_id,
        profiles=["ranking"], tags=tags, **values,
    )


def _frame(values, points):
    return gpd.GeoDataFrame(
        values, geometry=[Point(*point) for point in points], crs="EPSG:4326"
    )


def _layers():
    return [
        LayerMeta(
            id="houses", name="בתים", provider="ranking",
            source_url="memory://houses", display_field="name",
        ),
        _layer(
            "faults", "קווי שבר",
            ["rank:proximity", "rank:distance_m:2000", "rank:weight:0.5"],
        ),
        _layer(
            "soil", "קרקע רגישה",
            [
                "rank:density", "rank:distance_m:2000",
                "rank:saturation_count:2", "rank:weight:0.2",
            ],
        ),
        _layer(
            "age", "גיל מבנה",
            [
                "rank:attribute", "rank:field:build_year",
                "rank:min:1980", "rank:max:1920", "rank:weight:0.3",
            ],
        ),
        _layer("broken", "שכבה שבורה", ["rank:proximity"]),
        LayerMeta(
            id="ignored", name="לא מדרגים", provider="ranking",
            source_url="memory://ignored", tags=["rank:proximity"],
        ),
    ]


def _frames():
    return {
        "houses": _frame(
            {
                "id": ["h1", "h2", "h3"],
                "name": ["בית ישן", "בית חדש", "בית רחוק"],
                "build_year": [1925, 1975, 1930],
            },
            [(34.8000, 32.0800), (34.8005, 32.0800), (34.8090, 32.0800)],
        ),
        "faults": _frame({"id": ["f1"]}, [(34.8000, 32.0800)]),
        "soil": _frame(
            {"id": ["s1", "s2"]},
            [(34.8001, 32.0800), (34.8002, 32.0800)],
        ),
        "broken": _frame({"id": ["x"]}, [(34.8000, 32.0800)]),
        "ignored": _frame({"id": ["i"]}, [(34.8000, 32.0800)]),
    }


def _service(layers=None):
    registry = InMemoryProviderRegistry()
    registry.register("ranking", RankingProvider(_frames()))
    catalog = CatalogService(FakeLayersRepository(layers or _layers()), registry)
    return RankingService(catalog, registry)


def test_ranking_orders_features_by_total_weighted_score():
    result = _service().rank(BOUNDARY, "houses", now=NOW)

    assert result.subject_feature_count == 3
    # 1925 on the fault outranks 1930 further out, which outranks 1975 nearby.
    assert [feature.label for feature in result.features] == [
        "בית ישן", "בית רחוק", "בית חדש"
    ]
    assert [feature.rank for feature in result.features] == [1, 2, 3]
    scores = [feature.total_score for feature in result.features]
    assert scores == sorted(scores, reverse=True)


def test_ranking_keeps_every_rule_contribution_with_evidence():
    result = _service().rank(BOUNDARY, "houses", now=NOW)

    top = result.features[0]
    assert {item.kind for item in top.contributions} == {
        "proximity", "density", "attribute"
    }
    proximity = next(
        item for item in top.contributions if item.kind == "proximity"
    )
    assert proximity.measured_distance_m == 0.0
    assert proximity.raw_score == 1.0
    assert proximity.weighted_score == pytest.approx(0.5)
    assert proximity.evidence[0].feature_id == "f1"
    density = next(item for item in top.contributions if item.kind == "density")
    assert density.matched_count == 2


def test_ranking_normalizes_against_successful_rule_weights():
    result = _service().rank(BOUNDARY, "houses", now=NOW)

    assert result.max_possible_score == pytest.approx(1.0)
    top = result.features[0]
    assert top.normalized_score == pytest.approx(
        top.total_score / result.max_possible_score, abs=1e-4
    )
    assert top.normalized_score <= 1.0


def test_ranking_inverted_attribute_range_scores_older_buildings_higher():
    result = _service().rank(BOUNDARY, "houses", now=NOW)

    by_label = {feature.label: feature for feature in result.features}
    old = next(
        item for item in by_label["בית ישן"].contributions
        if item.kind == "attribute"
    )
    new = next(
        item for item in by_label["בית חדש"].contributions
        if item.kind == "attribute"
    )
    assert old.raw_score > new.raw_score
    assert old.raw_score == pytest.approx(0.9167, abs=1e-3)


def test_ranking_keeps_partial_results_when_one_rule_fails():
    result = _service().rank(BOUNDARY, "houses", now=NOW)

    assert result.applied_rule_count == 4
    assert result.successful_rule_count == 3
    assert len(result.failures) == 1
    assert result.failures[0].layer_id == "broken"
    assert result.failures[0].error_type == "RuntimeError"
    assert "unavailable" in result.failures[0].message


def test_ranking_ignores_layers_without_the_ranking_profile():
    result = _service().rank(BOUNDARY, "houses", now=NOW)

    rule_ids = {
        item.rule_layer_id
        for feature in result.features for item in feature.contributions
    }
    assert "ignored" not in rule_ids


def test_ranking_scores_zero_when_no_rule_matches():
    layers = [
        LayerMeta(
            id="houses", name="בתים", provider="ranking",
            source_url="memory://houses", display_field="name",
        ),
        # The nearest fault sits ~50 m away, outside this 1 m radius.
        _layer(
            "soil", "קרקע רגישה",
            ["rank:proximity", "rank:distance_m:1", "rank:weight:0.5"],
        ),
    ]

    result = _service(layers).rank(BOUNDARY, "houses", now=NOW)

    assert result.max_possible_score == pytest.approx(0.5)
    assert all(feature.total_score == 0.0 for feature in result.features)
    assert all(feature.normalized_score == 0.0 for feature in result.features)


def test_ranking_rejects_a_layer_declaring_two_rule_kinds():
    layers = [
        LayerMeta(
            id="houses", name="בתים", provider="ranking",
            source_url="memory://houses",
        ),
        _layer("faults", "קווי שבר", ["rank:proximity", "rank:density"]),
    ]

    result = _service(layers).rank(BOUNDARY, "houses", now=NOW)

    assert result.successful_rule_count == 0
    assert result.failures[0].error_type == "ValueError"
    assert "exactly one rule kind" in result.failures[0].message


def test_ranking_rejects_inverted_window():
    with pytest.raises(ValueError, match="window_start"):
        _service().rank(
            BOUNDARY, "houses",
            window_start=datetime(2026, 7, 25, tzinfo=timezone.utc),
            window_end=NOW,
        )


def test_ranking_applies_the_requested_limit():
    result = _service().rank(BOUNDARY, "houses", limit=1, now=NOW)

    assert len(result.features) == 1
    assert result.subject_feature_count == 3
    assert result.features[0].label == "בית ישן"


def test_ranking_endpoint_exposes_score_and_coverage_contract():
    app = FastAPI()
    app.include_router(router)
    app.state.ranking = Mock()
    app.state.ranking.rank.return_value = RankingResult(
        generated_at=NOW, window_start=NOW, window_end=NOW,
        subject_layer_id="houses", subject_layer_name="בתים",
        subject_feature_count=3, applied_rule_count=2,
        successful_rule_count=1, max_possible_score=1.0,
    )
    app.state.request_log = Mock()

    response = TestClient(app).post("/api/ranking", json={
        "boundaries": mapping(MultiPolygon([BOUNDARY])),
        "subject_layer_id": "houses",
        "from": "2026-07-24T08:00:00+00:00",
        "to": "2026-07-24T12:00:00+00:00",
    })

    assert response.status_code == 200
    assert response.json()["applied_rule_count"] == 2
    assert response.json()["successful_rule_count"] == 1
    call = app.state.ranking.rank.call_args
    assert call.kwargs["subject_layer_id"] == "houses"
    assert call.kwargs["window_start"] == datetime(
        2026, 7, 24, 8, 0, tzinfo=timezone.utc
    )


def test_ranking_endpoint_requires_timezone_aware_times():
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).post("/api/ranking", json={
        "boundaries": mapping(MultiPolygon([BOUNDARY])),
        "subject_layer_id": "houses",
        "from": "2026-07-24T08:00:00",
    })

    assert response.status_code == 422


def test_ranking_endpoint_requires_a_subject_layer():
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).post("/api/ranking", json={
        "boundaries": mapping(MultiPolygon([BOUNDARY])),
    })

    assert response.status_code == 422
