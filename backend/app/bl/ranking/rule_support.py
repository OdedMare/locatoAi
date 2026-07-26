"""Small shared helpers for deterministic rule scoring."""

from datetime import timezone

import pandas as pd

from app.bl.ranking.models.evidence import RankingEvidence

_ID_FIELDS = ("id", "objectid", "featureid", "entityid")
_EVIDENCE_LIMIT = 20


def require_field(data, field, role: str) -> str:
    if not field or field not in data.columns:
        raise ValueError("Ranking rule missing " + role + " field")
    return field


def clean_value(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def normalized_time(value):
    if value is None or pd.isna(value):
        return None
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(timezone.utc)
    return timestamp.tz_convert(timezone.utc).to_pydatetime()


def evidence_for(row, entity=None) -> RankingEvidence:
    return RankingEvidence(
        feature_id=str(row["_ranking_evidence_id"]),
        entity=clean_value(entity) or None,
        observed_at=normalized_time(row.get("_ranking_time")),
    )


def bounded_evidence(data, entity_field=None):
    return [
        evidence_for(row, row.get(entity_field) if entity_field else None)
        for _, row in data.head(_EVIDENCE_LIMIT).iterrows()
    ]


def evidence_id_field(data):
    by_name = {str(column).casefold(): column for column in data.columns}
    return next((by_name[name] for name in _ID_FIELDS if name in by_name), None)


def clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
