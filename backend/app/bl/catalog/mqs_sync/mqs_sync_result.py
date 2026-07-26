from dataclasses import dataclass


@dataclass
class MqsSyncResult:
    added: int = 0
    updated: int = 0
    skipped: int = 0

    @property
    def total(self) -> int:
        return self.added + self.updated + self.skipped
