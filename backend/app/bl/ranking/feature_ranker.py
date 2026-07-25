"""Turn per-rule contributions into a deterministic ranked feature list."""

from app.bl.ranking.models.ranked_feature import RankedFeature
from app.bl.ranking.rule_support import clean_value

_ROUNDING = 4


class FeatureRanker:
    def __init__(self, max_possible_score: float, limit: int) -> None:
        self._max_possible = max_possible_score
        self._limit = limit

    def rank(self, subjects, contributions, label_field):
        scored = [
            self._feature(index, row, contributions.get(index, []), label_field)
            for index, row in subjects.iterrows()
        ]
        ordered = sorted(scored, key=self._order)
        return [
            feature.model_copy(update={"rank": position})
            for position, feature in enumerate(ordered[:self._limit], start=1)
        ]

    @staticmethod
    def _order(feature):
        return (-feature.total_score, feature.feature_id)

    def _feature(self, index, row, contributions, label_field):
        total = sum(item.weighted_score for item in contributions)
        longitude, latitude = self._point(row)
        return RankedFeature(
            rank=0, feature_id=str(row["_ranking_evidence_id"]),
            label=self._label(row, label_field),
            total_score=round(total, _ROUNDING),
            max_possible_score=round(self._max_possible, _ROUNDING),
            normalized_score=self._normalized(total),
            longitude=longitude, latitude=latitude,
            contributions=sorted(
                contributions, key=lambda item: -item.weighted_score
            ),
        )

    def _normalized(self, total):
        if self._max_possible <= 0:
            return 0.0
        return round(min(1.0, total / self._max_possible), _ROUNDING)

    @staticmethod
    def _label(row, label_field):
        if not label_field:
            return None
        return clean_value(row.get(label_field)) or None

    @staticmethod
    def _point(row):
        geometry = row.get("geometry")
        if geometry is None or geometry.is_empty:
            return None, None
        centroid = geometry.centroid
        return round(centroid.x, 6), round(centroid.y, 6)
