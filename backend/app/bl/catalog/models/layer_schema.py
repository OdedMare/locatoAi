from typing import List, Optional

from pydantic import BaseModel, Field

from app.bl.catalog.models.layer_field import LayerField
from app.bl.catalog.models.layer_parameter import LayerParameter


class LayerSchema(BaseModel):
    """Schema of a layer as reported by its provider (fetched on demand)."""

    layer_id: str
    geometry_type: str
    fields: List[LayerField]
    parameters: List[LayerParameter] = Field(default_factory=list)
    source_name: str = ""
    source_description: str = ""
    entity_field: Optional[str] = None
    """Stable identity field for repeated observations, when declared."""
    temporal_field: Optional[str] = None
    """Name of the field holding this layer's event time, if any — set by
    the provider. None means the layer has no temporal dimension."""
    display_field: Optional[str] = None
    """Preferred human-readable label field for map results."""
