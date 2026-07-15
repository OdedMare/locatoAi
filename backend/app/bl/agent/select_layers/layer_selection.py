from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.bl.ports.layer_meta import LayerMeta


@dataclass
class LayerSelection:
    layers: List[LayerMeta] = field(default_factory=list)
    clarify: Optional[str] = None
    reasoning: str = ""
    token_usage: Optional[Dict[str, int]] = None
    """The model's short Hebrew 'why' — shown in the UI agent panel."""
    requested_layer_ids: List[str] = field(default_factory=list)
    """Raw IDs requested by the model, before unknown IDs are discarded."""
    dropped_layer_ids: List[str] = field(default_factory=list)
    """Hallucinated/unknown IDs discarded at the catalog boundary."""
