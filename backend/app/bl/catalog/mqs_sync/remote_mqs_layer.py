from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class RemoteMqsLayer:
    id: str
    name: str
    description: str
    tags: List[str]
    provider: str = "mqs"

    @property
    def source_url(self) -> str:
        return f"mqs://layer/{self.id}"
