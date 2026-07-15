from typing import Dict, Optional


class UsageAccumulator:
    """Sums token usage across build attempts."""

    def __init__(self) -> None:
        self.total: Optional[Dict[str, int]] = None

    def add(self, usage) -> None:
        if not isinstance(usage, dict):
            return
        if self.total is None:
            self.total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        for key in self.total:
            self.total[key] += int(usage.get(key, 0))
