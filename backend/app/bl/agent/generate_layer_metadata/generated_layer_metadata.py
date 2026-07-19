from dataclasses import dataclass, field
from typing import List

from app.bl.ports.layer_parameter import LayerParameter


@dataclass
class GeneratedLayerMetadata:
    description: str
    tags: List[str] = field(default_factory=list)
    sample_count: int = 0
    dynamic_parameters: List[str] = field(default_factory=list)
    """Names of the layer's dynamic (autocomplete-backed) parameters —
    the UI must let the user resolve each before the layer can be queried."""
    configurable_parameters: List[LayerParameter] = field(default_factory=list)
    """Required selectors the catalog must resolve before sampling. Configured
    metadata values are excluded so provider-owned secrets never reach the UI."""
    requires_sample_polygon: bool = False
    """The Cubes preview request needs a user-selected map polygon."""
