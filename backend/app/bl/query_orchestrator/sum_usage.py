from typing import Dict, Optional


class UsageAccumulator:
    @staticmethod
    def sum(*usages) -> Optional[Dict[str, int]]:
        total: Optional[Dict[str, int]] = None
        for usage in usages:
            if not isinstance(usage, dict):
                continue
            if total is None:
                total = UsageAccumulator._empty()
            for key in total:
                total[key] += int(usage.get(key, 0))
        return total

    @staticmethod
    def _empty() -> Dict[str, int]:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


sum_usage = UsageAccumulator.sum
