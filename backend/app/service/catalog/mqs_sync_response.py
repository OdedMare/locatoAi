"""MQS catalog sync response."""

from pydantic import BaseModel


class MqsSyncResponse(BaseModel):
    added: int
    updated: int
    skipped: int
    total: int
