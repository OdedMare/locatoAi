"""Operational visibility for the MQS freshness target."""

from typing import Any, Dict, List

from fastapi import APIRouter, Request

from app.bl.ports.mqs_mirror import MqsMirror

router = APIRouter()


@router.get("/api/mqs-mirror/status")
def mirror_status(request: Request) -> List[Dict[str, Any]]:
    mirror: MqsMirror = request.app.state.mqs_mirror
    max_age = request.app.state.mqs_mirror_max_staleness_seconds
    return mirror.status(max_age)
