from dataclasses import dataclass, field
from typing import List


@dataclass
class GeneratedLayerMetadata:
    description: str
    tags: List[str] = field(default_factory=list)
    sample_count: int = 0
