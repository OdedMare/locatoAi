"""Health endpoint."""

from app.common.flapi_workers import abandoned_workers


def status() -> dict:
    return {
        "status": "ok",
        "flapi_abandoned_workers": abandoned_workers(),
    }
