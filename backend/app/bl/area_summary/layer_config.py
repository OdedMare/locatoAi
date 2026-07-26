"""Read area-summary behavior from existing catalog profiles and tags."""

from typing import Optional

_KINDS = ("count", "presence", "recommendation", "encounter")


def is_summary_layer(layer) -> bool:
    return "area-summary" in {profile.casefold() for profile in layer.profiles}


def summary_kind(layer) -> str:
    tags = {tag.casefold() for tag in layer.tags}
    matches = [kind for kind in _KINDS if "summary:" + kind in tags]
    if len(matches) != 1:
        raise ValueError(
            "Area summary layer must declare exactly one summary kind"
        )
    return matches[0]


def configured_field(layer, role: str) -> Optional[str]:
    prefix = ("summary:" + role + ":").casefold()
    match = next(
        (tag for tag in layer.tags if tag.casefold().startswith(prefix)), None
    )
    return match[len(prefix):].strip() if match else None


def resolved_field(layer, schema, role: str, *fallbacks) -> Optional[str]:
    configured = configured_field(layer, role)
    return configured or next((field for field in fallbacks if field), None)
