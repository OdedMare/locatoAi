from typing import Dict

from app.bl.executor.ops.base.op_handler import OpHandler
from app.bl.executor.ops.base.op_registration import OpRegistration

_REGISTRY: Dict[str, OpHandler] = {}


def register_op(op_name: str) -> OpRegistration:
    return OpRegistration(_REGISTRY, op_name)


def get_op_handler(op_name: str) -> OpHandler:
    handler = _REGISTRY.get(op_name)
    if handler is None:
        raise KeyError(f"No handler registered for op '{op_name}'")
    return handler
