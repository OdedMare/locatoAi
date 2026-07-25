"""Accept FLAPI's boolean ``metadata.isPartialSuccess`` in flunks."""

import logging
from typing import Any, Tuple, Union, get_args

_FIELDS = ("isPartialSuccess", "is_partial_success")
_logger = logging.getLogger(__name__)


class FlunksMetadataPatch:
    """Widens the one incorrect flunks response field."""

    @classmethod
    def apply(cls, flow_models: Any = None) -> bool:
        flow_models = flow_models or cls._models()
        if flow_models is None:
            return False
        metadata = getattr(flow_models, "MetaData", None)
        results = getattr(flow_models, "FlowResults", None)
        field = cls._field(metadata)
        if field is None:
            _logger.warning("flunks patch skipped: partial-success field missing")
            return False
        admitted = cls._types(field.annotation)
        if str not in admitted or bool in admitted:
            _logger.info("flunks patch not needed: %r", field.annotation)
            return False
        field.annotation = Union[bool, field.annotation]
        return cls._rebuild(metadata, results)

    @staticmethod
    def _models() -> Any:
        try:
            from flunks import flow_models
            return flow_models
        except ImportError:
            _logger.warning("flunks patch skipped: flunks not importable")
            return None

    @staticmethod
    def _types(annotation: Any) -> Tuple[Any, ...]:
        return get_args(annotation) or (annotation,)

    @staticmethod
    def _field(metadata: Any) -> Any:
        fields = getattr(metadata, "model_fields", {})
        for name, field in fields.items():
            if name in _FIELDS or getattr(field, "alias", None) in _FIELDS:
                return field
        return None

    @staticmethod
    def _rebuild(metadata: Any, results: Any) -> bool:
        if metadata is None or results is None:
            _logger.warning("flunks patch skipped: response models missing")
            return False
        try:
            # Pydantic embeds child schemas: the child must be rebuilt first.
            metadata.model_rebuild(force=True)
            results.model_rebuild(force=True)
        except Exception:
            _logger.exception("flunks patch rebuild failed")
            return False
        _logger.info("flunks patch applied: MetaData -> FlowResults")
        return True
