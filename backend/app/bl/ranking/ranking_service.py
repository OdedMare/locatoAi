"""Score every subject feature in a polygon against declarative rule layers."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from app.bl.executor.ops.base.execution_context import ExecutionContext
from app.bl.ranking.feature_loader import RankingFeatureLoader
from app.bl.ranking.feature_ranker import FeatureRanker
from app.bl.ranking.models.layer_failure import RankingLayerFailure
from app.bl.ranking.models.result import RankingResult
from app.bl.ranking.rule_config import (
    is_ranking_layer,
    numeric_field,
    rule_kind,
    weight,
)
from app.bl.ranking.rule_scorers import score_rule
from app.common.utils.geo_utils import buffer_wgs84_geometry

_DEFAULT_LIMIT = 200


class RankingService:
    def __init__(self, catalog, providers) -> None:
        self._catalog = catalog
        self._providers = providers

    def rank(
        self, boundaries, subject_layer_id: str,
        window_start=None, window_end=None, limit: int = _DEFAULT_LIMIT,
        now: Optional[datetime] = None,
    ) -> RankingResult:
        generated_at = self._aware(now or datetime.now(timezone.utc))
        end = self._aware(window_end or generated_at)
        start = self._aware(window_start or end - timedelta(hours=24))
        if start > end:
            raise ValueError("Ranking window_start must not exceed window_end")
        subject = self._catalog.get_layer(subject_layer_id)
        return self._rank_subject(
            subject, boundaries, start, end, generated_at, limit
        )

    def _rank_subject(self, subject, boundaries, start, end, generated_at, limit):
        context = ExecutionContext(
            catalog=self._catalog, providers=self._providers,
            user_geometry=boundaries, now=generated_at,
        )
        loader = RankingFeatureLoader(self._catalog, context)
        subjects, schema = loader.load(subject, boundaries, start, end)
        rules = self._rules(subject.id)
        return self._build(
            subject, schema, subjects, rules, loader, boundaries,
            start, end, generated_at, limit,
        )

    def _rules(self, subject_layer_id):
        return [
            layer for layer in self._catalog.list_queryable_layers()
            if is_ranking_layer(layer) and layer.id != subject_layer_id
        ]

    def _build(
        self, subject, schema, subjects, rules, loader, boundaries,
        start, end, generated_at, limit,
    ):
        contributions, failures, successful, possible = self._apply(
            rules, subjects, loader, boundaries, start, end
        )
        ranker = FeatureRanker(possible, limit)
        label_field = subject.display_field or schema.display_field
        return RankingResult(
            generated_at=generated_at, window_start=start, window_end=end,
            subject_layer_id=subject.id, subject_layer_name=subject.name,
            subject_feature_count=len(subjects),
            applied_rule_count=len(rules), successful_rule_count=successful,
            max_possible_score=round(possible, 4),
            features=ranker.rank(subjects, contributions, label_field),
            failures=failures,
        )

    def _apply(self, rules, subjects, loader, boundaries, start, end):
        contributions, failures, successful, possible = {}, [], 0, 0.0
        for layer in rules:
            try:
                scores = self._rule_scores(
                    layer, subjects, loader, boundaries, start, end
                )
                self._merge(contributions, scores)
                possible += weight(layer)
                successful += 1
            except Exception as exc:
                failures.append(self._failure(layer, exc))
        return contributions, failures, successful, possible

    def _rule_scores(self, layer, subjects, loader, boundaries, start, end):
        kind = rule_kind(layer)
        if kind == "attribute":
            return score_rule(kind, subjects, None, layer)
        rule_data, _ = loader.load(
            layer, boundaries, start, end,
            geometry=self._rule_geometry(layer, boundaries),
        )
        return score_rule(kind, subjects, rule_data, layer)

    @staticmethod
    def _rule_geometry(layer, boundaries):
        radius_m = numeric_field(layer, "distance_m", 500.0)
        if radius_m <= 0:
            raise ValueError("Ranking rank:distance_m must be positive")
        return buffer_wgs84_geometry(boundaries, radius_m)

    @staticmethod
    def _merge(contributions, scores):
        for index, contribution in scores.items():
            contributions.setdefault(index, []).append(contribution)

    @staticmethod
    def _failure(layer, error):
        return RankingLayerFailure(
            layer_id=layer.id, layer_name=layer.name,
            error_type=type(error).__name__,
            message=(str(error) or type(error).__name__)[:240],
        )

    @staticmethod
    def _aware(value):
        if value.utcoffset() is None:
            raise ValueError("Ranking times must include a timezone")
        return value.astimezone(timezone.utc)
