"""Relax flunks' ``MetaData.isPartialSuccess`` to accept a JSON boolean.

flunks declares ``FlowResults.metadata.isPartialSuccess`` as ``str``, but FLAPI
sends a real JSON boolean. Pydantic v2 does not coerce ``bool`` -> ``str``, so
deserializing an otherwise successful package response raises::

    1 validation error for FlowResults
    metadata.isPartialSuccess
      Input should be a valid string [type=string_type, input_value=False, ...]

The failure is inside flunks' own response parsing, after the HTTP call has
already succeeded, so there is no seam in ``FlunksRunner`` for us to intercept —
widening the annotation before the runner parses anything is the only fix
available from this side.

TEMPORARY: delete this module once flunks types the field as
``Union[bool, str]`` upstream. Nothing here changes request behavior; it only
widens what a response is allowed to contain.
"""

from typing import Any, Tuple, Union, get_args

_FIELD = "isPartialSuccess"


def _annotations(annotation: Any) -> Tuple[Any, ...]:
    """The concrete types an annotation admits.

    ``Optional[str]`` is ``Union[str, None]``, not ``str``, so an identity test
    against ``str`` would skip the patch and leave the bug in place.
    """
    args = get_args(annotation)
    return args or (annotation,)


def _rebuild_all(flow_models: Any) -> bool:
    """Force-rebuild every pydantic model in flunks' response module.

    Parents are rebuilt as well as ``MetaData`` itself; a model that fails to
    rebuild is skipped so one unrelated shape change cannot break the provider.
    """
    rebuilt = False
    for name in dir(flow_models):
        model = getattr(flow_models, name, None)
        if not hasattr(model, "model_rebuild"):
            continue
        try:
            model.model_rebuild(force=True)
            rebuilt = True
        except Exception:
            continue
    return rebuilt


class FlunksMetadataPatch:
    """Widens the ``isPartialSuccess`` annotation on flunks' ``MetaData``."""

    @staticmethod
    def apply() -> bool:
        """Rebuild ``MetaData`` so ``isPartialSuccess`` accepts bool or str.

        Returns whether the patch was applied. Import-time failures are
        swallowed: if flunks changes shape or fixes the field itself, the
        provider must keep working rather than fail to import.
        """
        try:
            from flunks import flow_models
        except ImportError:
            return False
        field = getattr(flow_models, "MetaData", None)
        field = field and field.model_fields.get(_FIELD)
        if field is None or str not in _annotations(field.annotation):
            return False  # already fixed upstream, or no longer a str field
        field.annotation = Union[bool, str]
        # Rebuilding MetaData alone is NOT enough. Pydantic v2 inlines a child's
        # core schema into every parent that embeds it, so `FlowResults` — the
        # model flunks actually validates, and the one named in the error —
        # keeps its stale `str` validator for `metadata.isPartialSuccess`.
        # Every model referencing MetaData must be rebuilt, not just MetaData.
        return _rebuild_all(flow_models)
