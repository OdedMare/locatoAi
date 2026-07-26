"""Small shared helpers for evidence-backed fact extraction."""

from datetime import timezone

import pandas as pd

from app.bl.area_summary.models.evidence import AreaSummaryEvidence

_ID_FIELDS = ("id", "objectid", "featureid", "entityid")
_EVIDENCE_LIMIT = 20


def require_field(data, field, role: str) -> str:
    if not field or field not in data.columns:
        raise ValueError("Area summary missing " + role + " field")
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


def format_time(value) -> str:
    timestamp = normalized_time(value)
    return timestamp.strftime("%Y-%m-%d %H:%M UTC") if timestamp else ""


def evidence_for(row, entity=None) -> AreaSummaryEvidence:
    return AreaSummaryEvidence(
        feature_id=str(row["_summary_evidence_id"]),
        entity=clean_value(entity) or None,
        observed_at=normalized_time(row.get("_summary_time")),
    )


def bounded_evidence(data, entity_field=None):
    return [
        evidence_for(row, row.get(entity_field) if entity_field else None)
        for _, row in data.head(_EVIDENCE_LIMIT).iterrows()
    ]


def evidence_id_field(data):
    by_name = {str(column).casefold(): column for column in data.columns}
    return next((by_name[name] for name in _ID_FIELDS if name in by_name), None)
