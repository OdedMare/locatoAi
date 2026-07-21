"""Catalog connectivity status returned with settings."""

from typing import Optional

from pydantic import BaseModel


class CatalogStatus(BaseModel):
    ok: bool
    layer_count: Optional[int] = None
    error: Optional[str] = None
