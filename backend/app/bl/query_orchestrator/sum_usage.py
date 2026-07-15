from typing import Dict, Optional


def sum_usage(*usages) -> Optional[Dict[str, int]]:
    total: Optional[Dict[str, int]] = None
    for usage in usages:
        if not isinstance(usage, dict):
            continue
        if total is None:
            total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        for key in total:
            total[key] += int(usage.get(key, 0))
    return total
