from dataclasses import dataclass, field
from typing import List


@dataclass
class GeneratedLayerMetadata:
    description: str
    tags: List[str] = field(default_factory=list)
    sample_count: int = 0
    dynamic_parameters: List[str] = field(default_factory=list)
    """Names of the layer's dynamic (autocomplete-backed) parameters —
    the UI must let the user resolve each before the layer can be queried."""
