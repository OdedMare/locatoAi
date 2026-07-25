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

from typing import Union

_FIELD = "isPartialSuccess"


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
            from flunks.flow_models import MetaData
        except ImportError:
            return False
        field = MetaData.model_fields.get(_FIELD)
        if field is None or field.annotation is not str:
            return False  # already fixed upstream, or no longer a plain str
        field.annotation = Union[bool, str]
        MetaData.model_rebuild(force=True)
        return True
