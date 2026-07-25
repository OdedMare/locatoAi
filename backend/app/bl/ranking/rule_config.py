"""Read ranking behavior from existing catalog profiles and tags."""

from typing import Optional

RANKING_PROFILE = "ranking"
_KINDS = ("proximity", "density", "attribute")
_DIRECTIONS = ("closer_is_worse", "closer_is_better")


def is_ranking_layer(layer) -> bool:
    profiles = {profile.casefold() for profile in layer.profiles}
    return RANKING_PROFILE in profiles


def rule_kind(layer) -> str:
    tags = {tag.casefold() for tag in layer.tags}
    matches = [kind for kind in _KINDS if "rank:" + kind in tags]
    if len(matches) != 1:
        raise ValueError("Ranking layer must declare exactly one rule kind")
    return matches[0]


def configured_field(layer, role: str) -> Optional[str]:
    prefix = ("rank:" + role + ":").casefold()
    match = next(
        (tag for tag in layer.tags if tag.casefold().startswith(prefix)), None
    )
    return match[len(prefix):].strip() if match else None


def required_field(layer, role: str) -> str:
    value = configured_field(layer, role)
    if not value:
        raise ValueError("Ranking rule is missing rank:" + role)
    return value


def numeric_field(layer, role: str, default: float) -> float:
    raw = configured_field(layer, role)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        raise ValueError("Ranking rank:" + role + " must be numeric")


def weight(layer) -> float:
    value = numeric_field(layer, "weight", 1.0)
    if value <= 0:
        raise ValueError("Ranking rank:weight must be positive")
    return value


def direction(layer) -> str:
    value = configured_field(layer, "direction") or _DIRECTIONS[0]
    if value not in _DIRECTIONS:
        raise ValueError("Ranking rank:direction is unsupported")
    return value
